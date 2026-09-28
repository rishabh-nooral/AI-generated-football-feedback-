import os
from io import BytesIO

from flask import Flask, jsonify, render_template, request, redirect, url_for, session, send_file
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    get_connection,
    create_tables,
    delete_team as delete_team_from_database,
    permanently_delete_inactive_user
)

from gemini_service import (
    generate_player_feedback,
    generate_team_rollup
)


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

# Session security key. Set FLASK_SECRET_KEY in your environment for production.
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-development-secret-key"
)

create_tables()


# =========================================================
# AUTHENTICATION ACCESS CONTROL
# =========================================================

PUBLIC_ENDPOINTS = {
    "landing",
    "login",
    "register",
    "logout",
    "static"
}


@app.before_request
def require_login():

    if request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if "user_id" not in session:
        return redirect(url_for("login"))

    team_id = (request.view_args or {}).get("team_id")
    if team_id is not None and not session.get("is_admin"):
        connection = get_connection()
        owned_team = connection.execute(
            "SELECT 1 FROM teams WHERE team_id = ? AND user_id = ?",
            (team_id, session["user_id"])
        ).fetchone()
        connection.close()

        if not owned_team:
            return "Team not found.", 404

    return None


# =========================================================
# POSITIONS
# =========================================================

POSITIONS = [
    "Goalkeeper",
    "Right Back",
    "Centre Back",
    "Left Back",
    "Defensive Midfielder",
    "Central Midfielder",
    "Attacking Midfielder",
    "Right Wing",
    "Left Wing",
    "Striker",
    "Forward"
]


# =========================================================
# AUTHENTICATION LANDING PAGE
# =========================================================

@app.route("/")
def landing():

    return render_template("landing.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return redirect(
                url_for(
                    "login",
                    error="Username and password are required."
                )
            )

        connection = get_connection()

        user = connection.execute(
            """
            SELECT user_id, username, password_hash, is_admin
            FROM users
            WHERE username = ? AND is_active = 1
            """,
            (username,)
        ).fetchone()

        connection.close()

        if not user or not check_password_hash(
            user["password_hash"],
            password
        ):
            return redirect(
                url_for(
                    "login",
                    error="Invalid username or password."
                )
            )

        session.clear()
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["is_admin"] = bool(user["is_admin"])

        if session["is_admin"]:
            return redirect(url_for("admin_dashboard"))

        return redirect(url_for("home"))

    return render_template("login.html")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

def get_admin_dashboard_data():

    connection = get_connection()

    stats = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM users WHERE is_admin = 0 AND is_active = 1) AS user_count,
            (SELECT COUNT(*) FROM teams) AS team_count,
            (SELECT COUNT(*) FROM report_generations) AS report_count,
            (SELECT COUNT(*) FROM report_downloads) AS download_count
        """
    ).fetchone()

    teams = connection.execute(
        """
        SELECT
            t.team_id,
            t.user_id,
            t.team_name,
            u.username,
            COUNT(s.session_id) AS session_count
        FROM teams t
        LEFT JOIN users u ON u.user_id = t.user_id
        LEFT JOIN sessions s ON s.team_id = t.team_id
        GROUP BY t.team_id, t.team_name
        ORDER BY u.username COLLATE NOCASE, t.team_name COLLATE NOCASE
        """
    ).fetchall()

    users = connection.execute(
        """
        SELECT user_id, username, is_active, deleted_at
        FROM users
        WHERE is_admin = 0
        ORDER BY username COLLATE NOCASE
        """
    ).fetchall()

    connection.close()

    return {
        "user_count": stats["user_count"],
        "team_count": stats["team_count"],
        "report_count": stats["report_count"],
        "download_count": stats["download_count"],
        "users": [
            {
                "user_id": user["user_id"],
                "username": user["username"],
                "is_active": bool(user["is_active"]),
                "deleted_at": user["deleted_at"]
            }
            for user in users
        ],
        "teams": [
            {
                "team_id": team["team_id"],
                "user_id": team["user_id"],
                "username": team["username"],
                "team_name": team["team_name"],
                "session_count": team["session_count"]
            }
            for team in teams
        ]
    }


def admin_only():

    if not session.get("is_admin"):
        return redirect(url_for("home"))

    return None


@app.route("/admin")
def admin_dashboard():

    access_denied = admin_only()
    if access_denied:
        return access_denied

    return render_template(
        "admin_dashboard.html",
        dashboard=get_admin_dashboard_data()
    )


@app.route("/admin/api/dashboard")
def admin_dashboard_data():

    access_denied = admin_only()
    if access_denied:
        return access_denied

    return jsonify(get_admin_dashboard_data())


@app.route("/admin/user/<int:user_id>")
def admin_user_details(user_id):

    access_denied = admin_only()
    if access_denied:
        return access_denied

    connection = get_connection()
    user = connection.execute(
        "SELECT user_id, username, is_active, deleted_at FROM users WHERE user_id = ? AND is_admin = 0",
        (user_id,)
    ).fetchone()
    if not user:
        connection.close()
        return "User not found.", 404

    teams = connection.execute(
        """
        SELECT
            t.team_id,
            t.team_name,
            COUNT(s.session_id) AS session_count,
            COALESCE((SELECT COUNT(*) FROM report_generations rg
                WHERE rg.team_id = t.team_id), 0) AS report_count,
            COALESCE((SELECT COUNT(*) FROM report_downloads rd
                WHERE rd.team_id = t.team_id), 0) AS download_count
        FROM teams t
        LEFT JOIN sessions s ON s.team_id = t.team_id
        WHERE t.user_id = ?
        GROUP BY t.team_id, t.team_name
        ORDER BY t.team_name COLLATE NOCASE
        """,
        (user_id,)
    ).fetchall()

    team_details = []
    for team in teams:
        sessions = connection.execute(
            """
            SELECT session_type, COUNT(*) AS session_count
            FROM sessions
            WHERE team_id = ?
            GROUP BY session_type
            ORDER BY session_type
            """,
            (team["team_id"],)
        ).fetchall()
        team_details.append({
            "team_name": team["team_name"],
            "session_count": team["session_count"],
            "report_count": team["report_count"],
            "download_count": team["download_count"],
            "sessions": [
                {
                    "session_type": item["session_type"],
                    "session_count": item["session_count"]
                }
                for item in sessions
            ]
        })

    connection.close()
    return render_template(
        "admin_user_details.html",
        user=user,
        teams=team_details
    )


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):

    access_denied = admin_only()
    if access_denied:
        return access_denied

    permanently_delete_inactive_user(user_id)
    return redirect(url_for("admin_dashboard"))


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password or not confirm_password:
            return redirect(
                url_for(
                    "register",
                    error="All fields are required."
                )
            )

        if len(username) < 3:
            return redirect(
                url_for(
                    "register",
                    error="Username must contain at least 3 characters."
                )
            )

        if len(password) < 6:
            return redirect(
                url_for(
                    "register",
                    error="Password must contain at least 6 characters."
                )
            )

        if password != confirm_password:
            return redirect(
                url_for(
                    "register",
                    error="Passwords do not match."
                )
            )

        connection = get_connection()

        existing_user = connection.execute(
            """
            SELECT user_id
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if existing_user:
            connection.close()
            return redirect(
                url_for(
                    "register",
                    error="Username already exists."
                )
            )

        password_hash = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO users
            (username, password_hash)
            VALUES (?, ?)
            """,
            (username, password_hash)
        )

        connection.commit()
        connection.close()

        return redirect(
            url_for(
                "login",
                registered="1"
            )
        )

    return render_template("register.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("landing"))


@app.route("/delete-account", methods=["POST"])
def delete_account():

    user_id = session.get("user_id")

    if not user_id or session.get("is_admin"):
        return redirect(url_for("landing"))

    connection = get_connection()
    connection.execute(
        """
        UPDATE users
        SET is_active = 0, deleted_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND is_admin = 0
        """,
        (user_id,)
    )
    connection.commit()
    connection.close()

    session.clear()

    return redirect(url_for("landing"))


# =========================================================
# EXISTING HOME / TEAM DASHBOARD LIST
# =========================================================

@app.route("/dashboard")
def home():

    connection = get_connection()

    teams = connection.execute(
        """
        SELECT
            t.*,

            (
                SELECT COUNT(*)
                FROM players p
                WHERE p.team_id = t.team_id
            ) AS player_count,

            (
                SELECT COUNT(*)
                FROM sessions s
                WHERE s.team_id = t.team_id
            ) AS session_count

        FROM teams t

        WHERE t.user_id = ?

        ORDER BY t.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "create_team.html",
        teams=teams
    )


# =========================================================
# CREATE TEAM
# =========================================================

@app.route(
    "/create-team",
    methods=["POST"]
)
def create_team():

    team_name = request.form.get(
        "team_name",
        ""
    ).strip()

    if not team_name:

        return redirect(
            url_for("home")
        )

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO teams (user_id, team_name)
            VALUES (?, ?)
            """,
            (session["user_id"], team_name)
        )

        team_id = cursor.lastrowid

        connection.commit()

        return redirect(
            url_for(
                "setup_players",
                team_id=team_id
            )
        )

    except Exception as error:

        connection.rollback()

        return (
            f"Could not create team: {error}",
            400
        )

    finally:

        connection.close()


# =========================================================
# SETUP PLAYERS
# =========================================================

@app.route(
    "/setup-players/<int:team_id>"
)
def setup_players(team_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ? AND user_id = ?
        """,
        (team_id, session["user_id"])
    ).fetchone()

    connection.close()

    if not team:

        return "Team not found.", 404

    return render_template(
        "setup_players.html",
        team=team,
        positions=POSITIONS
    )


# =========================================================
# SAVE PLAYERS
# =========================================================

@app.route(
    "/save-players/<int:team_id>",
    methods=["POST"]
)
def save_players(team_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ? AND user_id = ?
        """,
        (team_id, session["user_id"])
    ).fetchone()

    if not team:

        connection.close()

        return "Team not found.", 404

    players = []

    used_positions = set()

    used_jerseys = set()

    try:

        for index in range(1, 12):

            player_name = request.form.get(
                f"player_name_{index}",
                ""
            ).strip()

            position = request.form.get(
                f"position_{index}",
                ""
            ).strip()

            jersey_number = request.form.get(
                f"jersey_number_{index}",
                ""
            ).strip()

            if not player_name:

                raise ValueError(
                    f"Player {index}: name is required."
                )

            if position not in POSITIONS:

                raise ValueError(
                    f"Player {index}: invalid position."
                )

            if position in used_positions:

                raise ValueError(
                    f"Position '{position}' is used more than once."
                )

            used_positions.add(position)

            if not jersey_number:

                raise ValueError(
                    f"Player {index}: jersey number is required."
                )

            try:

                jersey_number = int(
                    jersey_number
                )

            except ValueError:

                raise ValueError(
                    f"Player {index}: jersey number must be a number."
                )

            if jersey_number in used_jerseys:

                raise ValueError(
                    f"Jersey number {jersey_number} is used more than once."
                )

            used_jerseys.add(
                jersey_number
            )

            players.append(
                (
                    player_name,
                    position,
                    jersey_number
                )
            )

        if len(players) != 11:

            raise ValueError(
                "Exactly 11 players are required."
            )

        if used_positions != set(POSITIONS):

            missing_positions = [
                position
                for position in POSITIONS
                if position not in used_positions
            ]

            raise ValueError(
                "Missing position(s): "
                + ", ".join(missing_positions)
            )

        for player in players:

            connection.execute(
                """
                INSERT INTO players
                (
                    team_id,
                    player_name,
                    position,
                    jersey_number
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    team_id,
                    player[0],
                    player[1],
                    player[2]
                )
            )

        connection.commit()

        return redirect(
            url_for(
                "team_dashboard",
                team_id=team_id
            )
        )

    except Exception as error:

        connection.rollback()

        return (
            f"Could not save players: {error}",
            400
        )

    finally:

        connection.close()


# =========================================================
# TEAM DASHBOARD
# =========================================================

@app.route(
    "/team/<int:team_id>"
)
def team_dashboard(team_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ? AND user_id = ?
        """,
        (team_id, session["user_id"])
    ).fetchone()

    if not team:

        connection.close()

        return "Team not found.", 404

    players = connection.execute(
        """
        SELECT *
        FROM players
        WHERE team_id = ?
        ORDER BY jersey_number
        """,
        (team_id,)
    ).fetchall()

    sessions = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE team_id = ?
        ORDER BY session_date DESC, session_id DESC
        """,
        (team_id,)
    ).fetchall()

    existing_positions = {
        player["position"]
        for player in players
    }

    missing_positions = [
        position
        for position in POSITIONS
        if position not in existing_positions
    ]

    starting_players = [
        player for player in players
        if not player["is_substitute"]
    ]
    substitute_players = [
        player for player in players
        if player["is_substitute"]
    ]

    connection.close()

    return render_template(
        "team_dashboard.html",
        team=team,
        players=players,
        starting_players=starting_players,
        substitute_players=substitute_players,
        sessions=sessions,
        positions=POSITIONS,
        missing_positions=missing_positions
    )


# =========================================================
# ADD REPLACEMENT PLAYER
# =========================================================

@app.route(
    "/team/<int:team_id>/add-replacement",
    methods=["GET", "POST"]
)
def add_replacement(team_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    if not team:

        connection.close()

        return "Team not found.", 404

    existing_players = connection.execute(
        """
        SELECT *
        FROM players
        WHERE team_id = ?
        ORDER BY jersey_number
        """,
        (team_id,)
    ).fetchall()

    existing_positions = {
        player["position"]
        for player in existing_players
    }

    missing_positions = [
        position
        for position in POSITIONS
        if position not in existing_positions
    ]

    if request.method == "POST":

        player_name = request.form.get(
            "player_name",
            ""
        ).strip()

        position = request.form.get(
            "position",
            ""
        ).strip()

        jersey_number = request.form.get(
            "jersey_number",
            ""
        ).strip()

        if not player_name:

            connection.close()

            return "Player name is required.", 400

        if position not in missing_positions:

            connection.close()

            return (
                "This position is not currently available.",
                400
            )

        try:

            jersey_number = int(
                jersey_number
            )

        except ValueError:

            connection.close()

            return (
                "Jersey number must be a number.",
                400
            )

        duplicate_jersey = connection.execute(
            """
            SELECT player_id
            FROM players
            WHERE team_id = ?
            AND jersey_number = ?
            """,
            (
                team_id,
                jersey_number
            )
        ).fetchone()

        if duplicate_jersey:

            connection.close()

            return (
                "This jersey number is already used.",
                400
            )

        connection.execute(
            """
            INSERT INTO players
            (
                team_id,
                player_name,
                position,
                jersey_number
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                team_id,
                player_name,
                position,
                jersey_number
            )
        )

        connection.commit()

        connection.close()

        return redirect(
            url_for(
                "team_dashboard",
                team_id=team_id
            )
        )

    connection.close()

    return render_template(
        "add_replacement.html",
        team=team,
        missing_positions=missing_positions
    )


# =========================================================
# EDIT PLAYER
# =========================================================

@app.route(
    "/team/<int:team_id>/player/<int:player_id>/edit",
    methods=["GET", "POST"]
)
def edit_player(team_id, player_id):

    connection = get_connection()

    player = connection.execute(
        """
        SELECT *
        FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (
            player_id,
            team_id
        )
    ).fetchone()

    if not player:

        connection.close()

        return "Player not found.", 404

    if player["is_substitute"]:
        connection.close()
        return "Substitute players cannot be edited.", 403

    if request.method == "POST":

        player_name = request.form.get(
            "player_name",
            ""
        ).strip()

        position = request.form.get(
            "position",
            ""
        ).strip()

        jersey_number = request.form.get(
            "jersey_number",
            ""
        ).strip()

        if not player_name:

            connection.close()

            return "Player name is required.", 400

        if position not in POSITIONS:

            connection.close()

            return "Invalid position.", 400

        try:

            jersey_number = int(
                jersey_number
            )

        except ValueError:

            connection.close()

            return (
                "Jersey number must be a number.",
                400
            )

        duplicate_position = connection.execute(
            """
            SELECT player_id
            FROM players
            WHERE team_id = ?
            AND position = ?
            AND player_id != ?
            """,
            (
                team_id,
                position,
                player_id
            )
        ).fetchone()

        if duplicate_position:

            connection.close()

            return (
                "Another player already has this position.",
                400
            )

        duplicate_jersey = connection.execute(
            """
            SELECT player_id
            FROM players
            WHERE team_id = ?
            AND jersey_number = ?
            AND player_id != ?
            """,
            (
                team_id,
                jersey_number,
                player_id
            )
        ).fetchone()

        if duplicate_jersey:

            connection.close()

            return (
                "Another player already has this jersey number.",
                400
            )

        connection.execute(
            """
            UPDATE players
            SET
                player_name = ?,
                position = ?,
                jersey_number = ?
            WHERE player_id = ?
            AND team_id = ?
            """,
            (
                player_name,
                position,
                jersey_number,
                player_id,
                team_id
            )
        )

        connection.commit()

        connection.close()

        return redirect(
            url_for(
                "team_dashboard",
                team_id=team_id
            )
        )

    connection.close()

    return render_template(
        "edit_player.html",
        player=player,
        positions=POSITIONS,
        team_id=team_id
    )


# =========================================================
# EDIT PLAYER DATA API
# =========================================================

@app.route(
    "/api/team/<int:team_id>/player/<int:player_id>/edit-data",
    methods=["GET"]
)
def edit_player_data(team_id, player_id):

    connection = get_connection()

    player = connection.execute(
        """
        SELECT player_id, player_name, position, jersey_number
        FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (player_id, team_id)
    ).fetchone()

    team = connection.execute(
        """
        SELECT team_id, team_name
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    connection.close()

    if not player or not team:
        return {
            "success": False,
            "message": "Player or team not found."
        }, 404

    return {
        "success": True,
        "team": dict(team),
        "player": dict(player),
        "positions": POSITIONS
    }


# =========================================================
# DELETE PLAYER
# =========================================================

@app.route(
    "/team/<int:team_id>/player/<int:player_id>/delete",
    methods=["POST"]
)
def delete_player(team_id, player_id):

    connection = get_connection()

    player = connection.execute(
        """
        SELECT *
        FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (
            player_id,
            team_id
        )
    ).fetchone()

    if not player:

        connection.close()

        return "Player not found.", 404

    connection.execute(
        """
        DELETE FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (
            player_id,
            team_id
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        url_for(
            "team_dashboard",
            team_id=team_id
        )
    )


# =========================================================
# DELETE ENTIRE TEAM
# =========================================================

@app.route(
    "/delete-team/<int:team_id>",
    methods=["POST"]
)
def delete_team(team_id):

    deleted = delete_team_from_database(
        team_id
    )

    if not deleted:

        return "Team not found.", 404

    return redirect(
        url_for("home")
    )


# =========================================================
# DELETE SESSION
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/delete",
    methods=["POST"]
)
def delete_session(team_id, session_id):

    connection = get_connection()

    session_record = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    ).fetchone()

    if not session_record:

        connection.close()

        return "Session not found.", 404

    connection.execute(
        """
        DELETE FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "team_dashboard",
            team_id=team_id
        )
    )


# =========================================================
# CREATE SESSION
# =========================================================

@app.route(
    "/team/<int:team_id>/create-session",
    methods=["GET", "POST"]
)
def create_session(team_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    if not team:

        connection.close()

        return "Team not found.", 404

    if request.method == "POST":

        session_date = request.form.get(
            "session_date",
            ""
        ).strip()

        session_type = request.form.get(
            "session_type",
            ""
        ).strip()

        opponent = request.form.get(
            "opponent",
            ""
        ).strip()

        if not session_date:

            connection.close()

            return "Session date is required.", 400

        if session_type not in [
            "Training",
            "Match"
        ]:

            connection.close()

            return "Invalid session type.", 400

        connection.execute(
            """
            INSERT INTO sessions
            (
                team_id,
                session_date,
                session_type,
                opponent
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                team_id,
                session_date,
                session_type,
                opponent
            )
        )

        connection.commit()

        session_id = connection.execute(
            """
            SELECT last_insert_rowid()
            """
        ).fetchone()[0]

        connection.close()

        return redirect(
            url_for(
                "session_details",
                team_id=team_id,
                session_id=session_id
            )
        )

    connection.close()

    return render_template(
        "create_session.html",
        team=team
    )


# =========================================================
# SESSION DETAILS
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>"
)
def session_details(team_id, session_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    session = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    ).fetchone()

    if not team or not session:

        connection.close()

        return "Session not found.", 404

    if session["session_type"] == "Match":
        players = connection.execute(
            """
            SELECT DISTINCT p.*
            FROM players p
            LEFT JOIN substitutions s ON s.player_in_id = p.player_id
            WHERE p.team_id = ?
            AND (p.is_substitute = 0 OR s.session_id = ?)
            ORDER BY p.is_substitute, p.jersey_number
            """,
            (team_id, session_id)
        ).fetchall()
    else:
        players = connection.execute(
            """
            SELECT *
            FROM players
            WHERE team_id = ? AND is_substitute = 0
            ORDER BY jersey_number
            """,
            (team_id,)
        ).fetchall()

    observations = connection.execute(
        """
        SELECT *
        FROM player_observations
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchall()

    observation_map = {
        observation["player_id"]: observation
        for observation in observations
    }

    team_observation = connection.execute(
        """
        SELECT *
        FROM team_observations
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    connection.close()

    return render_template(
        "session_details.html",
        team=team,
        session=session,
        players=players,
        observation_map=observation_map,
        team_observation=team_observation
    )


# =========================================================
# SESSION DETAILS DATA API
# =========================================================

@app.route(
    "/api/team/<int:team_id>/session/<int:session_id>/details",
    methods=["GET"]
)
def session_details_data(team_id, session_id):

    connection = get_connection()

    team = connection.execute(
        "SELECT * FROM teams WHERE team_id = ?",
        (team_id,)
    ).fetchone()

    session_record = connection.execute(
        """
        SELECT * FROM sessions
        WHERE session_id = ? AND team_id = ?
        """,
        (session_id, team_id)
    ).fetchone()

    if not team or not session_record:
        connection.close()
        return {
            "success": False,
            "message": "Team or session not found."
        }, 404

    if session_record["session_type"] == "Match":
        players = connection.execute(
            """
            SELECT DISTINCT p.player_id, p.player_name, p.position,
                            p.jersey_number, p.is_substitute
            FROM players p
            LEFT JOIN substitutions s ON s.player_in_id = p.player_id
            WHERE p.team_id = ?
            AND (p.is_substitute = 0 OR s.session_id = ?)
            ORDER BY p.is_substitute, p.jersey_number
            """,
            (team_id, session_id)
        ).fetchall()
    else:
        players = connection.execute(
            """
            SELECT player_id, player_name, position, jersey_number,
                   is_substitute
            FROM players
            WHERE team_id = ? AND is_substitute = 0
            ORDER BY jersey_number
            """,
            (team_id,)
        ).fetchall()

    team_observation = connection.execute(
        """
        SELECT team_observation
        FROM team_observations
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    player_observations = connection.execute(
        """
        SELECT player_id, coach_observation
        FROM player_observations
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchall()

    feedback_rows = connection.execute(
        """
        SELECT player_id, feedback
        FROM ai_feedback
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchall()

    stats_rows = connection.execute(
        """
        SELECT player_id, goals, yellow_cards, red_cards, minutes_played
        FROM match_player_stats
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchall()

    connection.close()

    return {
        "success": True,
        "team": {
            "team_id": team["team_id"],
            "team_name": team["team_name"]
        },
        "session": {
            "session_id": session_record["session_id"],
            "session_type": session_record["session_type"],
            "session_date": session_record["session_date"],
            "opponent": session_record["opponent"] or ""
        },
        "players": [dict(player) for player in players],
        "team_observation": (
            team_observation["team_observation"]
            if team_observation else ""
        ),
        "observation_map": {
            str(row["player_id"]): row["coach_observation"]
            for row in player_observations
        },
        "ai_feedback_map": {
            str(row["player_id"]): row["feedback"]
            for row in feedback_rows
        },
        "stats_map": {
            str(row["player_id"]): {
                "goals": row["goals"] or 0,
                "yellow_cards": row["yellow_cards"] or 0,
                "red_cards": row["red_cards"] or 0,
                "minutes_played": row["minutes_played"] or 0
            }
            for row in stats_rows
        }
    }


# =========================================================
# SAVE TEAM OBSERVATION
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/team-observation",
    methods=["POST"]
)
def save_team_observation(team_id, session_id):

    payload = request.get_json(silent=True) or request.form
    team_observation = str(
        payload.get("team_observation", "")
    ).strip()

    if not team_observation:

        return (
            "Team observation cannot be empty.",
            400
        )

    connection = get_connection()

    session = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    ).fetchone()

    if not session:

        connection.close()

        return "Session not found.", 404

    existing = connection.execute(
        """
        SELECT team_observation_id, team_observation
        FROM team_observations
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()

    if existing:

        connection.execute(
            """
            INSERT INTO team_observation_history
            (session_id, team_observation)
            VALUES (?, ?)
            """,
            (session_id, existing["team_observation"])
        )

        connection.execute(
            """
            UPDATE team_observations
            SET team_observation = ?
            WHERE session_id = ?
            """,
            (
                team_observation,
                session_id
            )
        )

    else:

        connection.execute(
            """
            INSERT INTO team_observations
            (
                session_id,
                team_observation
            )
            VALUES (?, ?)
            """,
            (
                session_id,
                team_observation
            )
        )

    connection.commit()

    connection.close()

    if request.is_json:
        return {
            "success": True,
            "message": "Team observation saved successfully."
        }

    return redirect(
        url_for(
            "session_details",
            team_id=team_id,
            session_id=session_id
        )
    )


# =========================================================
# PLAYER OBSERVATION
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/observation",
    methods=["GET", "POST"]
)
def player_observation(
    team_id,
    session_id,
    player_id
):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    session = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    ).fetchone()

    player = connection.execute(
        """
        SELECT *
        FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (
            player_id,
            team_id
        )
    ).fetchone()

    if not team or not session or not player:

        connection.close()

        return "Player or session not found.", 404

    if player["is_substitute"]:
        is_match_substitute = connection.execute(
            """
            SELECT 1
            FROM substitutions
            WHERE session_id = ? AND player_in_id = ?
            """,
            (session_id, player_id)
        ).fetchone()
        if session["session_type"] != "Match" or not is_match_substitute:
            connection.close()
            return "Player or session not found.", 404

    existing_observation = connection.execute(
        """
        SELECT *
        FROM player_observations
        WHERE session_id = ?
        AND player_id = ?
        """,
        (
            session_id,
            player_id
        )
    ).fetchone()

    if request.method == "POST":

        coach_observation = request.form.get(
            "coach_observation",
            ""
        ).strip()

        if not coach_observation:

            connection.close()

            return (
                "Coach observation cannot be empty.",
                400
            )

        if existing_observation:

            connection.execute(
                """
                UPDATE player_observations
                SET coach_observation = ?
                WHERE session_id = ?
                AND player_id = ?
                """,
                (
                    coach_observation,
                    session_id,
                    player_id
                )
            )

        else:

            connection.execute(
                """
                INSERT INTO player_observations
                (
                    session_id,
                    player_id,
                    coach_observation
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    player_id,
                    coach_observation
                )
            )

        connection.commit()

        connection.close()

        return redirect(
            url_for(
                "session_details",
                team_id=team_id,
                session_id=session_id
            )
        )

    connection.close()

    return render_template(
        "player_observation.html",
        team=team,
        session=session,
        player=player,
        observation=existing_observation
    )


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/save-player-observation",
    methods=["POST"]
)
def save_player_observation(team_id, session_id):

    payload = request.get_json(silent=True) or request.form
    player_id = payload.get("player_id")
    coach_observation = str(
        payload.get("coach_observation", "")
    ).strip()

    if not player_id or not coach_observation:
        return {
            "success": False,
            "message": "Player and observation are required."
        }, 400

    connection = get_connection()

    player = connection.execute(
        """
        SELECT player_id, player_name, is_substitute
        FROM players
        WHERE player_id = ? AND team_id = ?
        """,
        (player_id, team_id)
    ).fetchone()
    session_record = connection.execute(
        """
        SELECT session_id
        FROM sessions
        WHERE session_id = ? AND team_id = ?
        """,
        (session_id, team_id)
    ).fetchone()

    if not player or not session_record:
        connection.close()
        return {
            "success": False,
            "message": "Player or session not found."
        }, 404

    if player["is_substitute"]:
        match_substitute = connection.execute(
            """
            SELECT 1
            FROM substitutions s
            JOIN sessions session_record
                ON session_record.session_id = s.session_id
            WHERE s.session_id = ?
            AND s.player_in_id = ?
            AND session_record.session_type = 'Match'
            """,
            (session_id, player_id)
        ).fetchone()
        if not match_substitute:
            connection.close()
            return {
                "success": False,
                "message": "Substitute observations are available only in their match."
            }, 404

    existing = connection.execute(
        """
        SELECT observation_id, coach_observation
        FROM player_observations
        WHERE session_id = ? AND player_id = ?
        """,
        (session_id, player_id)
    ).fetchone()

    if existing:
        connection.execute(
            """
            INSERT INTO player_observation_history
            (session_id, player_id, coach_observation)
            VALUES (?, ?, ?)
            """,
            (session_id, player_id, existing["coach_observation"])
        )
        connection.execute(
            """
            UPDATE player_observations
            SET coach_observation = ?, created_at = CURRENT_TIMESTAMP
            WHERE observation_id = ?
            """,
            (coach_observation, existing["observation_id"])
        )
    else:
        connection.execute(
            """
            INSERT INTO player_observations
            (session_id, player_id, coach_observation)
            VALUES (?, ?, ?)
            """,
            (session_id, player_id, coach_observation)
        )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "message": "Player observation saved successfully.",
        "player_id": int(player_id),
        "session_id": session_id
    }


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/delete-feedback-history",
    methods=["POST"]
)
def delete_feedback_history(team_id, session_id, player_id):

    connection = get_connection()
    valid = connection.execute(
        """
        SELECT 1 FROM players p
        JOIN sessions s ON s.team_id = p.team_id
        WHERE p.player_id = ? AND p.team_id = ? AND s.session_id = ?
        """,
        (player_id, team_id, session_id)
    ).fetchone()

    if not valid:
        connection.close()
        return "Player or session not found.", 404

    connection.execute(
        "DELETE FROM feedback_history WHERE session_id = ? AND player_id = ?",
        (session_id, player_id)
    )
    connection.execute(
        "DELETE FROM ai_feedback WHERE session_id = ? AND player_id = ?",
        (session_id, player_id)
    )
    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "feedback_history",
            team_id=team_id,
            session_id=session_id,
            player_id=player_id
        )
    )


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/team-summary-history"
)
def team_summary_history(team_id, session_id):

    connection = get_connection()
    team = connection.execute(
        "SELECT * FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()
    session_record = connection.execute(
        "SELECT * FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()

    if not team or not session_record:
        connection.close()
        return "Team or session not found.", 404

    history = connection.execute(
        """
        SELECT team_summary_history_id, summary, created_at
        FROM team_summary_history
        WHERE team_id = ? AND session_id = ?
        ORDER BY team_summary_history_id DESC
        """,
        (team_id, session_id)
    ).fetchall()
    connection.close()

    return render_template(
        "team_summary_history.html",
        team=team,
        session=session_record,
        history=history
    )


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/delete-team-summary-history",
    methods=["POST"]
)
def delete_team_summary_history(team_id, session_id):

    connection = get_connection()
    valid = connection.execute(
        "SELECT 1 FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()

    if not valid:
        connection.close()
        return "Team or session not found.", 404

    connection.execute(
        "DELETE FROM team_summary_history WHERE team_id = ? AND session_id = ?",
        (team_id, session_id)
    )
    connection.commit()
    connection.close()

    return redirect(
        url_for(
            "team_summary_history",
            team_id=team_id,
            session_id=session_id
        )
    )


def _pdf_escape(value):
    return (str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>"))


def _build_pdf(title, sections):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=14
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        spaceBefore=10,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=8
    )
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )
    story = [Paragraph(_pdf_escape(title), title_style)]
    for heading, value in sections:
        story.append(Paragraph(_pdf_escape(heading), heading_style))
        story.append(Paragraph(_pdf_escape(value), body_style))
    document.build(story)
    buffer.seek(0)
    return buffer


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/download-feedback-pdf"
)
def download_player_feedback_pdf(team_id, session_id, player_id):

    connection = get_connection()
    team = connection.execute(
        "SELECT * FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()
    session_record = connection.execute(
        "SELECT * FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()
    player = connection.execute(
        "SELECT * FROM players WHERE player_id = ? AND team_id = ?",
        (player_id, team_id)
    ).fetchone()
    feedback = connection.execute(
        "SELECT feedback, created_at FROM ai_feedback WHERE session_id = ? AND player_id = ?",
        (session_id, player_id)
    ).fetchone()
    observation = connection.execute(
        "SELECT coach_observation FROM player_observations WHERE session_id = ? AND player_id = ?",
        (session_id, player_id)
    ).fetchone()
    connection.close()

    if not team or not session_record or not player:
        return "Team, session, or player not found.", 404
    if player["is_substitute"] and session_record["session_type"] != "Match":
        return "Substitute feedback is available only in matches.", 404
    if not feedback:
        return "No AI feedback has been generated for this player yet.", 404

    download_connection = get_connection()
    download_connection.execute(
        """
        INSERT INTO report_downloads (report_type, user_id, team_id)
        VALUES ('individual', ?, ?)
        """,
        (session.get("user_id"), team_id)
    )
    download_connection.commit()
    download_connection.close()

    buffer = _build_pdf(
        "AI Player Coaching Feedback",
        [
            ("Team", team["team_name"]),
            ("Session", f"{session_record['session_type']} - {session_record['session_date']}"),
            ("Player", player["player_name"]),
            ("Position", player["position"]),
            ("Coach Observation", observation["coach_observation"] if observation else "No observation saved."),
            ("AI Feedback", feedback["feedback"])
        ]
    )
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"player_ai_feedback_{player_id}_session_{session_id}.pdf"
    )


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/download-team-summary-pdf"
)
def download_team_summary_pdf(team_id, session_id):

    connection = get_connection()
    team = connection.execute(
        "SELECT * FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()
    session_record = connection.execute(
        "SELECT * FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()
    summary = connection.execute(
        """
        SELECT summary, created_at FROM team_summary_history
        WHERE team_id = ? AND session_id = ?
        ORDER BY team_summary_history_id DESC LIMIT 1
        """,
        (team_id, session_id)
    ).fetchone()
    observation = connection.execute(
        "SELECT team_observation FROM team_observations WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    connection.close()

    if not team or not session_record:
        return "Team or session not found.", 404
    if not summary:
        return "No team AI report has been generated for this session yet.", 404

    download_connection = get_connection()
    download_connection.execute(
        """
        INSERT INTO report_downloads (report_type, user_id, team_id)
        VALUES ('team', ?, ?)
        """,
        (session.get("user_id"), team_id)
    )
    download_connection.commit()
    download_connection.close()

    buffer = _build_pdf(
        "AI Team Coaching Report",
        [
            ("Team", team["team_name"]),
            ("Session", f"{session_record['session_type']} - {session_record['session_date']}"),
            ("Team Observation", observation["team_observation"] if observation else "No team observation saved."),
            ("AI Team Report", summary["summary"])
        ]
    )
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"team_ai_report_{team_id}_session_{session_id}.pdf"
    )

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/team-observation-history/view"
)
def team_observation_history_page(team_id, session_id):

    connection = get_connection()
    session_record = connection.execute(
        """
        SELECT session_id FROM sessions
        WHERE session_id = ? AND team_id = ?
        """,
        (session_id, team_id)
    ).fetchone()
    connection.close()

    if not session_record:
        return "Session not found.", 404

    return render_template("team_observation_history.html")


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/observation-history/view"
)
def player_observation_history_page(team_id, session_id, player_id):

    connection = get_connection()
    player = connection.execute(
        "SELECT player_id FROM players WHERE player_id = ? AND team_id = ?",
        (player_id, team_id)
    ).fetchone()
    session_record = connection.execute(
        """
        SELECT session_id FROM sessions
        WHERE session_id = ? AND team_id = ?
        """,
        (session_id, team_id)
    ).fetchone()
    connection.close()

    if not player or not session_record:
        return "Player or session not found.", 404

    return render_template("player_observation_history.html")


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/team-observation-history"
)
def get_team_observation_history(team_id, session_id):

    connection = get_connection()
    session_record = connection.execute(
        "SELECT session_id FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()

    if not session_record:
        connection.close()
        return {"success": False, "message": "Session not found."}, 404

    current = connection.execute(
        """
        SELECT team_observation, created_at
        FROM team_observations WHERE session_id = ?
        """,
        (session_id,)
    ).fetchone()
    rows = connection.execute(
        """
        SELECT team_observation_history_id, team_observation, created_at
        FROM team_observation_history
        WHERE session_id = ? ORDER BY team_observation_history_id DESC
        """,
        (session_id,)
    ).fetchall()
    connection.close()

    return {
        "success": True,
        "current_observation": current["team_observation"] if current else "",
        "current_created_at": current["created_at"] if current else "",
        "history": [
            {
                "history_id": row["team_observation_history_id"],
                "observation": row["team_observation"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    }


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/team-observation-history/<int:history_id>",
    methods=["DELETE", "POST"]
)
def delete_team_observation_history(team_id, session_id, history_id):

    connection = get_connection()
    row = connection.execute(
        """
        SELECT h.team_observation_history_id
        FROM team_observation_history h
        JOIN sessions s ON s.session_id = h.session_id
        WHERE h.team_observation_history_id = ?
        AND h.session_id = ? AND s.team_id = ?
        """,
        (history_id, session_id, team_id)
    ).fetchone()

    if not row:
        connection.close()
        return {"success": False, "message": "History record not found."}, 404

    connection.execute(
        "DELETE FROM team_observation_history WHERE team_observation_history_id = ?",
        (history_id,)
    )
    connection.commit()
    connection.close()
    return {"success": True, "message": "History record deleted successfully."}


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/observation-history"
)
def get_player_observation_history(team_id, session_id, player_id):

    connection = get_connection()
    player = connection.execute(
        "SELECT * FROM players WHERE player_id = ? AND team_id = ?",
        (player_id, team_id)
    ).fetchone()
    session_record = connection.execute(
        "SELECT session_id FROM sessions WHERE session_id = ? AND team_id = ?",
        (session_id, team_id)
    ).fetchone()

    if not player or not session_record:
        connection.close()
        return {"success": False, "message": "Player or session not found."}, 404

    current = connection.execute(
        """
        SELECT coach_observation, created_at FROM player_observations
        WHERE session_id = ? AND player_id = ?
        """,
        (session_id, player_id)
    ).fetchone()
    rows = connection.execute(
        """
        SELECT player_observation_history_id, coach_observation, created_at
        FROM player_observation_history
        WHERE session_id = ? AND player_id = ?
        ORDER BY player_observation_history_id DESC
        """,
        (session_id, player_id)
    ).fetchall()
    connection.close()

    return {
        "success": True,
        "player": {
            "player_id": player["player_id"],
            "player_name": player["player_name"],
            "position": player["position"],
            "jersey_number": player["jersey_number"]
        },
        "current_observation": current["coach_observation"] if current else "",
        "current_created_at": current["created_at"] if current else "",
        "history": [
            {
                "history_id": row["player_observation_history_id"],
                "observation": row["coach_observation"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]
    }


@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/observation-history/<int:history_id>",
    methods=["DELETE", "POST"]
)
def delete_player_observation_history(team_id, session_id, player_id, history_id):

    connection = get_connection()
    row = connection.execute(
        """
        SELECT h.player_observation_history_id
        FROM player_observation_history h
        JOIN sessions s ON s.session_id = h.session_id
        JOIN players p ON p.player_id = h.player_id
        WHERE h.player_observation_history_id = ?
        AND h.session_id = ? AND h.player_id = ?
        AND s.team_id = ? AND p.team_id = ?
        """,
        (history_id, session_id, player_id, team_id, team_id)
    ).fetchone()

    if not row:
        connection.close()
        return {"success": False, "message": "History record not found."}, 404

    connection.execute(
        "DELETE FROM player_observation_history WHERE player_observation_history_id = ?",
        (history_id,)
    )
    connection.commit()
    connection.close()
    return {"success": True, "message": "History record deleted successfully."}


# =========================================================
# MATCH EVENTS
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/match-events",
    methods=["GET", "POST"]
)
def match_events(team_id, session_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    session = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (
            session_id,
            team_id
        )
    ).fetchone()

    if not team or not session:

        connection.close()

        return "Session not found.", 404

    if session["session_type"] != "Match":

        connection.close()

        return "Match events are only available for matches.", 400

    players = connection.execute(
        """
        SELECT *
        FROM players
        WHERE team_id = ?
        AND is_substitute = 0
        ORDER BY jersey_number
        """,
        (team_id,)
    ).fetchall()

    if request.method == "POST":

        try:
            substitution_count = int(
                request.form.get("substitution_count", "0") or 0
            )
        except ValueError:
            connection.close()
            return "Substitution count is invalid.", 400

        if substitution_count < 0 or substitution_count > 5:
            connection.close()
            return "A match can have a maximum of 5 substitutions.", 400

        for player in players:

            player_id = player["player_id"]

            goals = request.form.get(
                f"goals_{player_id}",
                "0"
            ).strip()

            yellow_cards = request.form.get(
                f"yellow_cards_{player_id}",
                "0"
            ).strip()

            red_cards = request.form.get(
                f"red_cards_{player_id}",
                "0"
            ).strip()

            minutes_played = request.form.get(
                f"minutes_played_{player_id}",
                "0"
            ).strip()

            try:

                goals = int(goals or 0)

                yellow_cards = int(
                    yellow_cards or 0
                )

                red_cards = int(
                    red_cards or 0
                )

                minutes_played = int(
                    minutes_played or 0
                )

            except ValueError:

                connection.close()

                return (
                    "Match statistics must be numbers.",
                    400
                )

            existing = connection.execute(
                """
                SELECT match_stat_id
                FROM match_player_stats
                WHERE session_id = ?
                AND player_id = ?
                """,
                (
                    session_id,
                    player_id
                )
            ).fetchone()

            if existing:

                connection.execute(
                    """
                    UPDATE match_player_stats
                    SET
                        goals = ?,
                        yellow_cards = ?,
                        red_cards = ?,
                        minutes_played = ?
                    WHERE session_id = ?
                    AND player_id = ?
                    """,
                    (
                        goals,
                        yellow_cards,
                        red_cards,
                        minutes_played,
                        session_id,
                        player_id
                    )
                )

            else:

                connection.execute(
                    """
                    INSERT INTO match_player_stats
                    (
                        session_id,
                        player_id,
                        goals,
                        yellow_cards,
                        red_cards,
                        minutes_played
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        player_id,
                        goals,
                        yellow_cards,
                        red_cards,
                        minutes_played
                    )
                )

        connection.commit()

        # -------------------------------------------------
        # SUBSTITUTIONS
        # -------------------------------------------------

        existing_substitution_count = connection.execute(
            "SELECT COUNT(*) AS count FROM substitutions WHERE session_id = ?",
            (session_id,)
        ).fetchone()["count"]

        if existing_substitution_count + substitution_count > 5:
            connection.close()
            return "A match can have a maximum of 5 substitutions.", 400

        used_outgoing_ids = set()

        for index in range(1, substitution_count + 1):
            player_out_id = request.form.get(f"player_out_{index}", "").strip()
            player_in_name = request.form.get(f"player_in_name_{index}", "").strip()
            player_in_jersey = request.form.get(f"player_in_jersey_{index}", "").strip()
            substitution_minute = request.form.get(
                f"substitution_minute_{index}", ""
            ).strip()

            if not player_out_id or not player_in_name or not player_in_jersey:
                connection.close()
                return "Incoming player name, jersey, and outgoing player are required.", 400

            try:
                player_out_id = int(player_out_id)
                player_in_jersey = int(player_in_jersey)
                substitution_minute = int(substitution_minute or 0)
            except ValueError:
                connection.close()
                return "Substitution information is invalid.", 400

            if substitution_minute < 0 or substitution_minute > 120:
                connection.close()
                return "Substitution minute must be between 0 and 120.", 400

            if player_out_id in used_outgoing_ids:
                connection.close()
                return "A player cannot be substituted out more than once.", 400

            player_out = connection.execute(
                """
                SELECT *
                FROM players
                WHERE player_id = ?
                AND team_id = ?
                AND is_substitute = 0
                """,
                (
                    player_out_id,
                    team_id
                )
            ).fetchone()

            if not player_out:
                connection.close()
                return "Outgoing player not found.", 400

            duplicate_jersey = connection.execute(
                """
                SELECT player_id
                FROM players
                WHERE team_id = ? AND jersey_number = ?
                """,
                (
                    team_id,
                    player_in_jersey
                )
            ).fetchone()

            if duplicate_jersey:
                connection.close()
                return "This jersey number is already used by the team.", 400

            substitute_position = f"Substitute {existing_substitution_count + index}"
            cursor = connection.execute(
                """
                INSERT INTO players
                (team_id, player_name, position, jersey_number, is_substitute)
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    team_id,
                    player_in_name,
                    substitute_position,
                    player_in_jersey
                )
            )
            player_in_id = cursor.lastrowid

            connection.execute(
                """
                INSERT INTO substitutions
                (session_id, player_out_id, player_in_id,
                 substitution_minute, position_at_substitution)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    player_out_id,
                    player_in_id,
                    substitution_minute,
                    player_out["position"]
                )
            )

            used_outgoing_ids.add(player_out_id)

        connection.commit()

        connection.close()

        return redirect(
            url_for(
                "match_events",
                team_id=team_id,
                session_id=session_id
            )
        )

    stats = connection.execute(
        """
        SELECT *
        FROM match_player_stats
        WHERE session_id = ?
        """,
        (session_id,)
    ).fetchall()

    substitutions = connection.execute(
        """
        SELECT
            s.*,
            out_player.player_name AS player_out_name,
            out_player.jersey_number AS player_out_jersey,
            out_player.position AS player_out_position,
            in_player.player_name AS player_in_name,
            in_player.jersey_number AS player_in_jersey,
            in_player.position AS player_in_position

        FROM substitutions s

        JOIN players out_player
            ON s.player_out_id = out_player.player_id

        JOIN players in_player
            ON s.player_in_id = in_player.player_id

        WHERE s.session_id = ?

        ORDER BY
            s.substitution_minute ASC
        """,
        (session_id,)
    ).fetchall()

    stats_map = {
        stat["player_id"]: stat
        for stat in stats
    }

    connection.close()

    return render_template(
        "match_events.html",
        team=team,
        session=session,
        players=players,
        stats_map=stats_map,
        substitutions=substitutions
    )


# =========================================================
# GENERATE INDIVIDUAL AI FEEDBACK
# =========================================================

@app.route(
    "/generate-feedback",
    methods=["POST"]
)
def generate_feedback():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        team_id = data.get(
            "team_id"
        )

        session_id = data.get(
            "session_id"
        )

        player_id = data.get(
            "player_id"
        )

        if not team_id or not session_id or not player_id:

            return {
                "success": False,
                "message":
                    "Missing team, session, or player ID."
            }, 400

        connection = get_connection()

        # -------------------------------------------------
        # TEAM
        # -------------------------------------------------

        team = connection.execute(
            """
            SELECT *
            FROM teams
            WHERE team_id = ?
            """,
            (team_id,)
        ).fetchone()

        # -------------------------------------------------
        # SESSION
        # -------------------------------------------------

        session_record = connection.execute(
            """
            SELECT *
            FROM sessions
            WHERE session_id = ?
            AND team_id = ?
            """,
            (
                session_id,
                team_id
            )
        ).fetchone()

        # -------------------------------------------------
        # PLAYER
        # -------------------------------------------------

        player = connection.execute(
            """
            SELECT *
            FROM players
            WHERE player_id = ?
            AND team_id = ?
            """,
            (
                player_id,
                team_id
            )
        ).fetchone()

        if not team:

            connection.close()

            return {
                "success": False,
                "message": "Team not found."
            }, 404

        if not session_record:

            connection.close()

            return {
                "success": False,
                "message": "Session not found."
            }, 404

        if not player:

            connection.close()

            return {
                "success": False,
                "message": "Player not found."
            }, 404

        if player["is_substitute"] and session_record["session_type"] != "Match":
            connection.close()
            return {
                "success": False,
                "message": "Substitute feedback is available only in matches."
            }, 404

        # -------------------------------------------------
        # PLAYER OBSERVATION
        # -------------------------------------------------

        observation = connection.execute(
            """
            SELECT coach_observation
            FROM player_observations
            WHERE session_id = ?
            AND player_id = ?
            """,
            (
                session_id,
                player_id
            )
        ).fetchone()

        if not observation:

            connection.close()

            return {
                "success": False,
                "message":
                    "Please add a player observation first."
            }, 400

        coach_observation = (
            observation["coach_observation"]
            or ""
        )

        # -------------------------------------------------
        # TEAM OBSERVATION
        # -------------------------------------------------

        team_observation = connection.execute(
            """
            SELECT team_observation
            FROM team_observations
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()

        team_notes = ""

        if team_observation:

            team_notes = (
                team_observation["team_observation"]
                or ""
            )

        # -------------------------------------------------
        # MATCH STATS
        # -------------------------------------------------

        match_stats = connection.execute(
            """
            SELECT *
            FROM match_player_stats
            WHERE session_id = ?
            AND player_id = ?
            """,
            (
                session_id,
                player_id
            )
        ).fetchone()

        goals = 0
        yellow_cards = 0
        red_cards = 0
        minutes_played = 0

        if match_stats:

            goals = match_stats["goals"] or 0

            yellow_cards = (
                match_stats["yellow_cards"]
                or 0
            )

            red_cards = (
                match_stats["red_cards"]
                or 0
            )

            minutes_played = (
                match_stats["minutes_played"]
                or 0
            )

        # -------------------------------------------------
        # SUBSTITUTIONS
        # -------------------------------------------------

        substitutions_rows = connection.execute(
            """
            SELECT
                s.*,
                out_player.player_name AS player_out_name,
                out_player.position AS player_out_position,
                in_player.player_name AS player_in_name,
                in_player.position AS player_in_position

            FROM substitutions s

            JOIN players out_player
                ON s.player_out_id = out_player.player_id

            JOIN players in_player
                ON s.player_in_id = in_player.player_id

            WHERE s.session_id = ?

            AND (
                s.player_out_id = ?
                OR s.player_in_id = ?
            )

            ORDER BY
                s.substitution_minute ASC
            """,
            (
                session_id,
                player_id,
                player_id
            )
        ).fetchall()

        substitutions = []

        for substitution in substitutions_rows:

            if substitution["player_out_id"] == player_id:

                substitutions.append(
                    {
                        "direction": "OUT",
                        "minute":
                            substitution[
                                "substitution_minute"
                            ],
                        "position_at_substitution":
                            substitution[
                                "position_at_substitution"
                            ]
                    }
                )

            elif substitution["player_in_id"] == player_id:

                substitutions.append(
                    {
                        "direction": "IN",
                        "minute":
                            substitution[
                                "substitution_minute"
                            ],
                        "position_at_substitution":
                            substitution[
                                "position_at_substitution"
                            ]
                    }
                )

        connection.close()

        # -------------------------------------------------
        # GENERATE GEMINI FEEDBACK
        # -------------------------------------------------

        feedback = generate_player_feedback(

            player_name=
                player["player_name"],

            position=
                player["position"],

            coach_observation=
                coach_observation,

            session_type=
                        session_record["session_type"],

            session_date=
                        session_record["session_date"],

            opponent=
                session_record["opponent"] or "",

            goals=goals,

            yellow_cards=
                yellow_cards,

            red_cards=
                red_cards,

            minutes_played=
                minutes_played,

            substitutions=
                substitutions,

            team_notes=
                team_notes
        )

        # =================================================
        # STEP 20 — SAVE AI FEEDBACK
        # =================================================

        save_connection = get_connection()

        existing_feedback = save_connection.execute(
            """
            SELECT feedback_id
            FROM ai_feedback
            WHERE session_id = ?
            AND player_id = ?
            """,
            (
                session_id,
                player_id
            )
        ).fetchone()

        # Save every generated version in feedback history.
        save_connection.execute(
            """
            INSERT INTO feedback_history
            (session_id, player_id, feedback)
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                player_id,
                feedback
            )
        )

        save_connection.execute(
            """
            INSERT INTO report_generations (report_type, user_id, team_id)
            VALUES ('individual', ?, ?)
            """,
            (session.get("user_id"), team_id)
        )

        if existing_feedback:

            # Keep ai_feedback as the latest feedback only.

            save_connection.execute(
                """
                UPDATE ai_feedback
                SET
                    feedback = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                AND player_id = ?
                """,
                (
                    feedback,
                    session_id,
                    player_id
                )
            )

        else:

            # First feedback for this player/session.

            save_connection.execute(
                """
                INSERT INTO ai_feedback
                (
                    session_id,
                    player_id,
                    feedback
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    player_id,
                    feedback
                )
            )

        save_connection.commit()

        # Get the saved feedback ID.

        saved_feedback = save_connection.execute(
            """
            SELECT
                feedback_id,
                created_at,
                updated_at
            FROM ai_feedback
            WHERE session_id = ?
            AND player_id = ?
            """,
            (
                session_id,
                player_id
            )
        ).fetchone()

        save_connection.close()

        # =================================================
        # RETURN RESULT
        # =================================================

        return {

            "success": True,

            "message":
                "AI feedback generated and saved successfully.",

            "feedback":
                feedback,

            "player_name":
                player["player_name"],

            "position":
                player["position"],

            "session_id":
                session_id,

            "player_id":
                player_id,

            "feedback_id":
                saved_feedback["feedback_id"]
                if saved_feedback
                else None
        }

    except Exception as error:

        return {

            "success": False,

            "message":
                f"Could not generate feedback: {error}"

        }, 500


# =========================================================
# FEEDBACK HISTORY
# =========================================================

@app.route(
    "/team/<int:team_id>/session/<int:session_id>/player/<int:player_id>/feedback-history"
)
def feedback_history(team_id, session_id, player_id):

    connection = get_connection()

    team = connection.execute(
        """
        SELECT *
        FROM teams
        WHERE team_id = ?
        """,
        (team_id,)
    ).fetchone()

    session = connection.execute(
        """
        SELECT *
        FROM sessions
        WHERE session_id = ?
        AND team_id = ?
        """,
        (session_id, team_id)
    ).fetchone()

    player = connection.execute(
        """
        SELECT *
        FROM players
        WHERE player_id = ?
        AND team_id = ?
        """,
        (player_id, team_id)
    ).fetchone()

    if not team or not session or not player:
        connection.close()
        return "Player or session not found.", 404

    history = connection.execute(
        """
        SELECT
            history_id,
            feedback,
            created_at
        FROM feedback_history
        WHERE session_id = ?
        AND player_id = ?
        ORDER BY history_id DESC
        """,
        (session_id, player_id)
    ).fetchall()

    connection.close()

    return render_template(
        "feedback_history.html",
        team=team,
        session=session,
        player=player,
        history=history
    )


# =========================================================
# GENERATE TEAM AI SUMMARY
# =========================================================

@app.route(
    "/generate-team-summary",
    methods=["POST"]
)
def generate_team_summary():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        team_id = data.get(
            "team_id"
        )

        session_id = data.get(
            "session_id"
        )

        player_feedback_list = data.get(
            "player_feedback",
            []
        )

        if not team_id or not session_id:

            return {

                "success": False,

                "message":
                    "Team ID and session ID are required."

            }, 400

        connection = get_connection()

        # -------------------------------------------------
        # TEAM
        # -------------------------------------------------

        team = connection.execute(
            """
            SELECT *
            FROM teams
            WHERE team_id = ?
            """,
            (team_id,)
        ).fetchone()

        # -------------------------------------------------
        # SESSION
        # -------------------------------------------------

        session_record = connection.execute(
            """
            SELECT *
            FROM sessions
            WHERE session_id = ?
            AND team_id = ?
            """,
            (
                session_id,
                team_id
            )
        ).fetchone()

        if not team:

            connection.close()

            return {

                "success": False,

                "message": "Team not found."

            }, 404

        if not session_record:

            connection.close()

            return {

                "success": False,

                "message": "Session not found."

            }, 404

        # -------------------------------------------------
        # TEAM OBSERVATION
        # -------------------------------------------------

        team_observation = connection.execute(
            """
            SELECT team_observation
            FROM team_observations
            WHERE session_id = ?
            """,
            (session_id,)
        ).fetchone()

        team_notes = ""

        if team_observation:

            team_notes = (
                team_observation["team_observation"]
                or ""
            )

        # -------------------------------------------------
        # IF FRONTEND DID NOT SEND FEEDBACK,
        # GENERATE INDIVIDUAL FEEDBACK FROM DATABASE
        # -------------------------------------------------

        if not player_feedback_list:

            players = connection.execute(
                """
                SELECT *
                FROM players
                WHERE team_id = ?
                ORDER BY jersey_number
                """,
                (team_id,)
            ).fetchall()

            player_feedback_list = []

            for player in players:

                observation = connection.execute(
                    """
                    SELECT coach_observation
                    FROM player_observations
                    WHERE session_id = ?
                    AND player_id = ?
                    """,
                    (
                        session_id,
                        player["player_id"]
                    )
                ).fetchone()

                if not observation:

                    continue

                # -------------------------------------------------
                # CHECK SAVED AI FEEDBACK FIRST
                # -------------------------------------------------

                saved_feedback = connection.execute(
                    """
                    SELECT feedback
                    FROM ai_feedback
                    WHERE session_id = ?
                    AND player_id = ?
                    """,
                    (
                        session_id,
                        player["player_id"]
                    )
                ).fetchone()

                # If feedback already exists, reuse it.
                # This avoids unnecessary Gemini API calls.

                if saved_feedback:

                    feedback = saved_feedback["feedback"]

                else:

                    match_stats = connection.execute(
                        """
                        SELECT *
                        FROM match_player_stats
                        WHERE session_id = ?
                        AND player_id = ?
                        """,
                        (
                            session_id,
                            player["player_id"]
                        )
                    ).fetchone()

                    goals = 0
                    yellow_cards = 0
                    red_cards = 0
                    minutes_played = 0

                    if match_stats:

                        goals = (
                            match_stats["goals"]
                            or 0
                        )

                        yellow_cards = (
                            match_stats["yellow_cards"]
                            or 0
                        )

                        red_cards = (
                            match_stats["red_cards"]
                            or 0
                        )

                        minutes_played = (
                            match_stats["minutes_played"]
                            or 0
                        )

                    substitution_rows = connection.execute(
                        """
                        SELECT *
                        FROM substitutions
                        WHERE session_id = ?

                        AND (
                            player_out_id = ?
                            OR player_in_id = ?
                        )

                        ORDER BY
                            substitution_minute ASC
                        """,
                        (
                            session_id,
                            player["player_id"],
                            player["player_id"]
                        )
                    ).fetchall()

                    substitutions = []

                    for substitution in substitution_rows:

                        if (
                            substitution["player_out_id"]
                            == player["player_id"]
                        ):

                            substitutions.append(
                                {
                                    "direction": "OUT",
                                    "minute":
                                        substitution[
                                            "substitution_minute"
                                        ],
                                    "position_at_substitution":
                                        substitution[
                                            "position_at_substitution"
                                        ]
                                }
                            )

                        elif (
                            substitution["player_in_id"]
                            == player["player_id"]
                        ):

                            substitutions.append(
                                {
                                    "direction": "IN",
                                    "minute":
                                        substitution[
                                            "substitution_minute"
                                        ],
                                    "position_at_substitution":
                                        substitution[
                                            "position_at_substitution"
                                        ]
                                }
                            )

                    feedback = generate_player_feedback(

                        player_name=
                            player["player_name"],

                        position=
                            player["position"],

                        coach_observation=
                            observation["coach_observation"],

                        session_type=
                            session_record["session_type"],

                        session_date=
                            session_record["session_date"],

                        opponent=
                            session_record["opponent"] or "",

                        goals=goals,

                        yellow_cards=
                            yellow_cards,

                        red_cards=
                            red_cards,

                        minutes_played=
                            minutes_played,

                        substitutions=
                            substitutions,

                        team_notes=
                            team_notes
                    )

                    # Save newly generated feedback.

                    existing_feedback = connection.execute(
                        """
                        SELECT feedback_id
                        FROM ai_feedback
                        WHERE session_id = ?
                        AND player_id = ?
                        """,
                        (
                            session_id,
                            player["player_id"]
                        )
                    ).fetchone()

                    if existing_feedback:

                        connection.execute(
                            """
                            UPDATE ai_feedback
                            SET
                                feedback = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE session_id = ?
                            AND player_id = ?
                            """,
                            (
                                feedback,
                                session_id,
                                player["player_id"]
                            )
                        )

                    else:

                        connection.execute(
                            """
                            INSERT INTO ai_feedback
                            (
                                session_id,
                                player_id,
                                feedback
                            )
                            VALUES (?, ?, ?)
                            """,
                            (
                                session_id,
                                player["player_id"],
                                feedback
                            )
                        )

                    connection.commit()

                player_feedback_list.append(
                    {
                        "player_name":
                            player["player_name"],

                        "position":
                            player["position"],

                        "feedback":
                            feedback
                    }
                )

        if not player_feedback_list:

            connection.close()

            return {

                "success": False,

                "message":
                    "No individual player feedback is available. Add player observations first."

            }, 400

        connection.close()

        # -------------------------------------------------
        # GENERATE TEAM SUMMARY
        # -------------------------------------------------

        team_summary = generate_team_rollup(

            player_feedback_list=
                player_feedback_list,

            team_observation=
                team_notes,

            session_type=
                session_record["session_type"],

            session_date=
                session_record["session_date"],

            opponent=
                session_record["opponent"] or ""
        )

        history_connection = get_connection()
        history_connection.execute(
            """
            INSERT INTO team_summary_history
            (session_id, team_id, summary)
            VALUES (?, ?, ?)
            """,
            (session_id, team_id, team_summary)
        )
        history_connection.execute(
            """
            INSERT INTO report_generations (report_type, user_id, team_id)
            VALUES ('team', ?, ?)
            """,
            (session.get("user_id"), team_id)
        )
        history_connection.commit()
        history_connection.close()

        return {

            "success": True,

            "team_summary":
                team_summary,

            "team_id":
                team_id,

            "session_id":
                session_id
        }

    except Exception as error:

        return {

            "success": False,

            "message":
                f"Could not generate team summary: {error}"

        }, 500


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )