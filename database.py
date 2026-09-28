# # import sqlite3


# # DATABASE_NAME = "football_coach.db"


# # def get_connection():

# #     connection = sqlite3.connect(DATABASE_NAME)

# #     connection.row_factory = sqlite3.Row

# #     # Enable foreign key support
# #     connection.execute("PRAGMA foreign_keys = ON")

# #     return connection


# # def create_tables():

# #     connection = get_connection()

# #     cursor = connection.cursor()


# #     # =====================================================
# #     # TEAMS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS teams (

# #             team_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             team_name TEXT NOT NULL UNIQUE,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# #         )
# #     """)


# #     # =====================================================
# #     # PLAYERS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS players (

# #             player_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             team_id INTEGER NOT NULL,

# #             player_name TEXT NOT NULL,

# #             position TEXT NOT NULL,

# #             jersey_number INTEGER,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (team_id)
# #                 REFERENCES teams(team_id)
# #                 ON DELETE CASCADE,

# #             UNIQUE(team_id, position),

# #             UNIQUE(team_id, jersey_number)
# #         )
# #     """)


# #     # =====================================================
# #     # SESSIONS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS sessions (

# #             session_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             team_id INTEGER NOT NULL,

# #             session_date TEXT NOT NULL,

# #             session_type TEXT NOT NULL
# #                 CHECK(session_type IN ('Training', 'Match')),

# #             opponent TEXT,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (team_id)
# #                 REFERENCES teams(team_id)
# #                 ON DELETE CASCADE
# #         )
# #     """)


# #     # =====================================================
# #     # TEAM OBSERVATIONS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS team_observations (

# #             team_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL UNIQUE,

# #             team_observation TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE
# #         )
# #     """)


# #     # =====================================================
# #     # PLAYER OBSERVATIONS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS player_observations (

# #             observation_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             player_id INTEGER NOT NULL,

# #             coach_observation TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (player_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE,

# #             UNIQUE(session_id, player_id)
# #         )
# #     """)


# #     # =====================================================
# #     # MATCH PLAYER STATS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS match_player_stats (

# #             match_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             player_id INTEGER NOT NULL,

# #             goals INTEGER DEFAULT 0,

# #             yellow_cards INTEGER DEFAULT 0,

# #             red_cards INTEGER DEFAULT 0,

# #             minutes_played INTEGER DEFAULT 0,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (player_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE,

# #             UNIQUE(session_id, player_id)
# #         )
# #     """)


# #     # =====================================================
# #     # SUBSTITUTIONS TABLE
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS substitutions (

# #             substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             player_out_id INTEGER NOT NULL,

# #             player_in_id INTEGER NOT NULL,

# #             substitution_minute INTEGER,

# #             position_at_substitution TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (player_out_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (player_in_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE
# #         )
# #     """)


# #     # =====================================================
# #     # AI FEEDBACK TABLE
# #     #
# #     # Stores ONLY the latest feedback for each
# #     # player/session combination.
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS ai_feedback (

# #             feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             player_id INTEGER NOT NULL,

# #             feedback TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (player_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE,

# #             UNIQUE(session_id, player_id)
# #         )
# #     """)


# #     # =====================================================
# #     # FEEDBACK HISTORY TABLE
# #     #
# #     # Stores EVERY generated version of AI feedback.
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS feedback_history (

# #             history_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             player_id INTEGER NOT NULL,

# #             feedback TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (player_id)
# #                 REFERENCES players(player_id)
# #                 ON DELETE CASCADE
# #         )
# #     """)


# #     # =====================================================
# #     # TEAM SUMMARY HISTORY TABLE
# #     #
# #     # Stores EVERY generated version of the team's
# #     # AI summary.
# #     #
# #     # Example:
# #     #
# #     # Version 1 -> first generated summary
# #     # Version 2 -> regenerated summary
# #     # Version 3 -> regenerated again
# #     #
# #     # This prevents older team summaries from being lost.
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE TABLE IF NOT EXISTS team_summary_history (

# #             team_summary_history_id INTEGER PRIMARY KEY AUTOINCREMENT,

# #             session_id INTEGER NOT NULL,

# #             team_id INTEGER NOT NULL,

# #             summary TEXT NOT NULL,

# #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

# #             FOREIGN KEY (session_id)
# #                 REFERENCES sessions(session_id)
# #                 ON DELETE CASCADE,

# #             FOREIGN KEY (team_id)
# #                 REFERENCES teams(team_id)
# #                 ON DELETE CASCADE
# #         )
# #     """)


# #     # =====================================================
# #     # INDEXES FOR PLAYER FEEDBACK HISTORY
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE INDEX IF NOT EXISTS
# #         idx_feedback_history_session_player
# #         ON feedback_history(session_id, player_id)
# #     """)


# #     cursor.execute("""
# #         CREATE INDEX IF NOT EXISTS
# #         idx_feedback_history_created_at
# #         ON feedback_history(created_at)
# #     """)


# #     # =====================================================
# #     # INDEXES FOR TEAM SUMMARY HISTORY
# #     # =====================================================

# #     cursor.execute("""
# #         CREATE INDEX IF NOT EXISTS
# #         idx_team_summary_history_session
# #         ON team_summary_history(session_id)
# #     """)


# #     cursor.execute("""
# #         CREATE INDEX IF NOT EXISTS
# #         idx_team_summary_history_team
# #         ON team_summary_history(team_id)
# #     """)


# #     cursor.execute("""
# #         CREATE INDEX IF NOT EXISTS
# #         idx_team_summary_history_created_at
# #         ON team_summary_history(created_at)
# #     """)


# #     # =====================================================
# #     # SAVE DATABASE CHANGES
# #     # =====================================================

# #     connection.commit()

# #     connection.close()


# # # =========================================================
# # # DELETE TEAM
# # # =========================================================

# # def delete_team(team_id):

# #     connection = get_connection()

# #     cursor = connection.cursor()

# #     cursor.execute(
# #         """
# #         DELETE FROM teams
# #         WHERE team_id = ?
# #         """,
# #         (team_id,)
# #     )

# #     deleted = cursor.rowcount

# #     connection.commit()

# #     connection.close()

# #     return deleted > 0


# # # =========================================================
# # # CREATE DATABASE
# # # =========================================================

# # if __name__ == "__main__":

# #     create_tables()

# #     print(
# #         "Database and tables created successfully."
# #     )




# import sqlite3


# DATABASE_NAME = "football_coach.db"


# def get_connection():

#     connection = sqlite3.connect(DATABASE_NAME)

#     connection.row_factory = sqlite3.Row

#     # Enable foreign key support
#     connection.execute("PRAGMA foreign_keys = ON")

#     return connection


# def create_tables():

#     connection = get_connection()

#     cursor = connection.cursor()


#     # =====================================================
#     # TEAMS TABLE
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS teams (

#             team_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             team_name TEXT NOT NULL UNIQUE,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         )
#     """)


#     # =====================================================
#     # PLAYERS TABLE
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS players (

#             player_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             team_id INTEGER NOT NULL,

#             player_name TEXT NOT NULL,

#             position TEXT NOT NULL,

#             jersey_number INTEGER,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (team_id)
#                 REFERENCES teams(team_id)
#                 ON DELETE CASCADE,

#             UNIQUE(team_id, position),

#             UNIQUE(team_id, jersey_number)
#         )
#     """)


#     # =====================================================
#     # SESSIONS TABLE
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS sessions (

#             session_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             team_id INTEGER NOT NULL,

#             session_date TEXT NOT NULL,

#             session_type TEXT NOT NULL
#                 CHECK(session_type IN ('Training', 'Match')),

#             opponent TEXT,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (team_id)
#                 REFERENCES teams(team_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # TEAM OBSERVATIONS TABLE
#     #
#     # Stores ONLY the current/latest team observation.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS team_observations (

#             team_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL UNIQUE,

#             team_observation TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # TEAM OBSERVATION HISTORY TABLE
#     #
#     # Stores older/past team observations.
#     #
#     # The current observation remains in team_observations.
#     # When a different observation is saved, the previous
#     # current observation is moved here.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS team_observation_history (

#             team_observation_history_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             team_observation TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # PLAYER OBSERVATIONS TABLE
#     #
#     # Stores ONLY the current/latest player observation.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS player_observations (

#             observation_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_id INTEGER NOT NULL,

#             coach_observation TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE,

#             UNIQUE(session_id, player_id)
#         )
#     """)


#     # =====================================================
#     # PLAYER OBSERVATION HISTORY TABLE
#     #
#     # Stores older/past player observations.
#     #
#     # The current observation remains in player_observations.
#     # When a different observation is saved, the previous
#     # current observation is moved here.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS player_observation_history (

#             player_observation_history_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_id INTEGER NOT NULL,

#             coach_observation TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # MATCH PLAYER STATS TABLE
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS match_player_stats (

#             match_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_id INTEGER NOT NULL,

#             goals INTEGER DEFAULT 0,

#             yellow_cards INTEGER DEFAULT 0,

#             red_cards INTEGER DEFAULT 0,

#             minutes_played INTEGER DEFAULT 0,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE,

#             UNIQUE(session_id, player_id)
#         )
#     """)


#     # =====================================================
#     # SUBSTITUTIONS TABLE
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS substitutions (

#             substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_out_id INTEGER NOT NULL,

#             player_in_id INTEGER NOT NULL,

#             substitution_minute INTEGER,

#             position_at_substitution TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (player_out_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_in_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # AI FEEDBACK TABLE
#     #
#     # Stores ONLY the latest feedback for each
#     # player/session combination.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS ai_feedback (

#             feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_id INTEGER NOT NULL,

#             feedback TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE,

#             UNIQUE(session_id, player_id)
#         )
#     """)


#     # =====================================================
#     # FEEDBACK HISTORY TABLE
#     #
#     # Stores EVERY generated version of AI feedback.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS feedback_history (

#             history_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             player_id INTEGER NOT NULL,

#             feedback TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (player_id)
#                 REFERENCES players(player_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # TEAM SUMMARY HISTORY TABLE
#     #
#     # Stores EVERY generated version of the team's
#     # AI summary.
#     # =====================================================

#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS team_summary_history (

#             team_summary_history_id INTEGER PRIMARY KEY AUTOINCREMENT,

#             session_id INTEGER NOT NULL,

#             team_id INTEGER NOT NULL,

#             summary TEXT NOT NULL,

#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#             FOREIGN KEY (session_id)
#                 REFERENCES sessions(session_id)
#                 ON DELETE CASCADE,

#             FOREIGN KEY (team_id)
#                 REFERENCES teams(team_id)
#                 ON DELETE CASCADE
#         )
#     """)


#     # =====================================================
#     # INDEXES FOR PLAYER FEEDBACK HISTORY
#     # =====================================================

#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_feedback_history_session_player
#         ON feedback_history(session_id, player_id)
#     """)


#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_feedback_history_created_at
#         ON feedback_history(created_at)
#     """)


#     # =====================================================
#     # INDEXES FOR TEAM SUMMARY HISTORY
#     # =====================================================

#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_team_summary_history_session
#         ON team_summary_history(session_id)
#     """)


#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_team_summary_history_team
#         ON team_summary_history(team_id)
#     """)


#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_team_summary_history_created_at
#         ON team_summary_history(created_at)
#     """)


#     # =====================================================
#     # INDEXES FOR TEAM OBSERVATION HISTORY
#     # =====================================================

#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_team_observation_history_session
#         ON team_observation_history(session_id)
#     """)


#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_team_observation_history_created_at
#         ON team_observation_history(created_at)
#     """)


#     # =====================================================
#     # INDEXES FOR PLAYER OBSERVATION HISTORY
#     # =====================================================

#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_player_observation_history_session_player
#         ON player_observation_history(session_id, player_id)
#     """)


#     cursor.execute("""
#         CREATE INDEX IF NOT EXISTS
#         idx_player_observation_history_created_at
#         ON player_observation_history(created_at)
#     """)


#     # =====================================================
#     # SAVE DATABASE CHANGES
#     # =====================================================

#     connection.commit()

#     connection.close()


# # =========================================================
# # DELETE TEAM
# # =========================================================

# def delete_team(team_id):

#     connection = get_connection()

#     cursor = connection.cursor()

#     cursor.execute(
#         """
#         DELETE FROM teams
#         WHERE team_id = ?
#         """,
#         (team_id,)
#     )

#     deleted = cursor.rowcount

#     connection.commit()

#     connection.close()

#     return deleted > 0


# # =========================================================
# # CREATE DATABASE
# # =========================================================

# if __name__ == "__main__":

#     create_tables()

#     print(
#         "Database and tables created successfully."
#     )





import sqlite3
from werkzeug.security import generate_password_hash


DATABASE_NAME = "football_coach.db"


def get_connection():

    connection = sqlite3.connect(DATABASE_NAME)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_tables():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    user_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(users)").fetchall()
    }

    if "is_admin" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
        )

    if "is_active" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
        )

    if "deleted_at" not in user_columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP"
        )

    cursor.execute(
        """
        INSERT OR IGNORE INTO users (username, password_hash, is_admin)
        VALUES (?, ?, 1)
        """,
        ("admin", generate_password_hash("admin143"))
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            team_name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
        )
    """)

    team_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(teams)").fetchall()
    }

    if "user_id" not in team_columns:
        cursor.execute("ALTER TABLE teams ADD COLUMN user_id INTEGER")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            position TEXT NOT NULL,
            jersey_number INTEGER,
            is_substitute INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE,
            UNIQUE(team_id, position),
            UNIQUE(team_id, jersey_number)
        )
    """)

    player_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(players)").fetchall()
    }

    if "is_substitute" not in player_columns:
        cursor.execute(
            "ALTER TABLE players ADD COLUMN is_substitute INTEGER NOT NULL DEFAULT 0"
        )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            session_type TEXT NOT NULL CHECK(session_type IN ('Training', 'Match')),
            opponent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_observations (
            team_observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            team_observation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_observation_history (
            team_observation_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            team_observation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_observations (
            observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            coach_observation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
            UNIQUE(session_id, player_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_observation_history (
            player_observation_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            coach_observation TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_player_stats (
            match_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            goals INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0,
            minutes_played INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
            UNIQUE(session_id, player_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS substitutions (
            substitution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_out_id INTEGER NOT NULL,
            player_in_id INTEGER NOT NULL,
            substitution_minute INTEGER,
            position_at_substitution TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_out_id) REFERENCES players(player_id) ON DELETE CASCADE,
            FOREIGN KEY (player_in_id) REFERENCES players(player_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
            UNIQUE(session_id, player_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_summary_history (
            team_summary_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams(team_id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_downloads (
            download_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL CHECK(report_type IN ('individual', 'team')),
            user_id INTEGER,
            team_id INTEGER,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    download_columns = {
        row["name"]
        for row in cursor.execute("PRAGMA table_info(report_downloads)").fetchall()
    }
    if "user_id" not in download_columns:
        cursor.execute("ALTER TABLE report_downloads ADD COLUMN user_id INTEGER")
    if "team_id" not in download_columns:
        cursor.execute("ALTER TABLE report_downloads ADD COLUMN team_id INTEGER")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_generations (
            generation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL CHECK(report_type IN ('individual', 'team')),
            user_id INTEGER,
            team_id INTEGER,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    indexes = [
        ("idx_feedback_history_session_player", "feedback_history(session_id, player_id)"),
        ("idx_feedback_history_created_at", "feedback_history(created_at)"),
        ("idx_team_summary_history_session", "team_summary_history(session_id)"),
        ("idx_team_summary_history_team", "team_summary_history(team_id)"),
        ("idx_team_summary_history_created_at", "team_summary_history(created_at)"),
        ("idx_team_observation_history_session", "team_observation_history(session_id)"),
        ("idx_team_observation_history_created_at", "team_observation_history(created_at)"),
        ("idx_player_observation_history_session_player", "player_observation_history(session_id, player_id)"),
        ("idx_player_observation_history_created_at", "player_observation_history(created_at)")
    ]

    for name, target in indexes:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")

    connection.commit()
    connection.close()


def delete_team(team_id):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
    deleted = cursor.rowcount
    connection.commit()
    connection.close()
    return deleted > 0


def permanently_delete_inactive_user(user_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        user = cursor.execute(
            """
            SELECT user_id
            FROM users
            WHERE user_id = ? AND is_admin = 0 AND is_active = 0
            """,
            (user_id,)
        ).fetchone()

        if not user:
            connection.close()
            return False

        team_ids = [
            row["team_id"]
            for row in cursor.execute(
                "SELECT team_id FROM teams WHERE user_id = ?",
                (user_id,)
            ).fetchall()
        ]

        cursor.execute(
            "DELETE FROM report_downloads WHERE user_id = ?",
            (user_id,)
        )
        cursor.execute(
            "DELETE FROM report_generations WHERE user_id = ?",
            (user_id,)
        )

        if team_ids:
            placeholders = ", ".join("?" for _ in team_ids)
            cursor.execute(
                f"DELETE FROM report_downloads WHERE team_id IN ({placeholders})",
                team_ids
            )
            cursor.execute(
                f"DELETE FROM report_generations WHERE team_id IN ({placeholders})",
                team_ids
            )

        cursor.execute("DELETE FROM teams WHERE user_id = ?", (user_id,))
        cursor.execute(
            "DELETE FROM users WHERE user_id = ? AND is_admin = 0 AND is_active = 0",
            (user_id,)
        )

        deleted = cursor.rowcount > 0
        connection.commit()
        connection.close()
        return deleted
    except Exception:
        connection.rollback()
        connection.close()
        raise


if __name__ == "__main__":
    create_tables()
    print("Database and tables created successfully.")
