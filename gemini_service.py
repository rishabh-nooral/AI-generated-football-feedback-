import os

from dotenv import load_dotenv
from google import genai


# =========================================================
# LOAD ENVIRONMENT
# =========================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY is not set in the .env file."
    )


# =========================================================
# GEMINI CLIENT
# =========================================================

client = genai.Client(
    api_key=api_key
)


MODEL_NAME = "gemini-3.6-flash"


def _get_value(item, key, default=""):

    if isinstance(item, dict):
        return item.get(key, default)

    try:
        return item[key]
    except (IndexError, KeyError, TypeError):
        return default


# =========================================================
# POSITION FOCUS
# =========================================================

POSITION_FOCUS = {

    "Goalkeeper": [
        "Shot stopping",
        "Handling",
        "Positioning",
        "Distribution",
        "Communication",
        "Cross management"
    ],

    "Right Back": [
        "1v1 defending",
        "Positioning",
        "Tackling",
        "Crossing",
        "Overlapping",
        "Defensive transitions"
    ],

    "Centre Back": [
        "Defensive positioning",
        "Tackling",
        "Aerial duels",
        "Passing",
        "Marking",
        "Communication"
    ],

    "Left Back": [
        "1v1 defending",
        "Positioning",
        "Tackling",
        "Crossing",
        "Overlapping",
        "Defensive transitions"
    ],

    "Defensive Midfielder": [
        "Ball recovery",
        "Positioning",
        "Passing",
        "Press resistance",
        "Defensive transitions",
        "Game awareness"
    ],

    "Central Midfielder": [
        "Passing",
        "Ball control",
        "Movement",
        "Creating passing options",
        "Press resistance",
        "Game awareness"
    ],

    "Attacking Midfielder": [
        "Chance creation",
        "Passing",
        "Movement",
        "Ball control",
        "Final-third decisions",
        "Attacking awareness"
    ],

    "Right Wing": [
        "1v1 attacking",
        "Dribbling",
        "Crossing",
        "Movement",
        "Finishing",
        "Defensive tracking"
    ],

    "Left Wing": [
        "1v1 attacking",
        "Dribbling",
        "Crossing",
        "Movement",
        "Finishing",
        "Defensive tracking"
    ],

    "Striker": [
        "Finishing",
        "Movement",
        "Hold-up play",
        "Positioning",
        "Pressing",
        "Chance conversion"
    ],

    "Forward": [
        "Finishing",
        "Movement",
        "Link-up play",
        "Dribbling",
        "Pressing",
        "Attacking decisions"
    ]
}


# =========================================================
# INDIVIDUAL PLAYER FEEDBACK
# =========================================================

def generate_player_feedback(
    player_name,
    position,
    coach_observation,
    session_type="Training",
    session_date="",
    opponent="",
    goals=0,
    yellow_cards=0,
    red_cards=0,
    minutes_played=0,
    substitutions=None,
    team_notes=""
):

    if substitutions is None:
        substitutions = []

    position_focus = POSITION_FOCUS.get(
        position,
        []
    )

    substitution_text = "No substitutions."

    if substitutions:

        substitution_lines = []

        for substitution in substitutions:

            direction = _get_value(
                substitution,
                "direction",
                ""
            )

            minute = _get_value(
                substitution,
                "minute",
                ""
            )

            position_at_substitution = _get_value(
                substitution,
                "position_at_substitution",
                ""
            )

            if direction == "OUT":

                substitution_lines.append(
                    f"Substituted OUT at minute {minute}, "
                    f"playing {position_at_substitution}."
                )

            elif direction == "IN":

                substitution_lines.append(
                    f"Substituted IN at minute {minute}, "
                    f"playing {position_at_substitution}."
                )

            else:

                substitution_lines.append(
                    f"Substitution at minute {minute}, "
                    f"position: {position_at_substitution}."
                )

        substitution_text = "\n".join(
            substitution_lines
        )

    team_notes_text = (
        team_notes.strip()
        if team_notes
        else "No specific team observation provided."
    )

    prompt = f"""
You are an expert football academy coach and coaching analyst.

Generate structured coaching feedback for ONE football player.

IMPORTANT RULES:

1. Use ONLY information provided in the input.
2. NEVER invent events, abilities, weaknesses, statistics,
   injuries, emotions, or performance details.
3. The player's registered position is important.
4. Use the position focus areas only to interpret the observation.
5. If a category is not supported by the observation or match data,
   write "No specific observation provided."
6. Keep feedback practical and suitable for a football coach.
7. Do not make medical or injury diagnoses.
8. Do not assume that a player performed well or badly unless
   the provided information supports it.
9. Suggested drills must be directly related to the supported
   improvement areas.
10. Team observation provides context only. Do not attribute
    team-level problems to the player unless the individual
    observation supports it.

PLAYER INFORMATION
------------------

Player:
{player_name}

Registered Position:
{position}

Position Focus Areas:
{", ".join(position_focus)}

SESSION INFORMATION
-------------------

Session Type:
{session_type}

Session Date:
{session_date}

Opponent:
{opponent if opponent else "Not applicable"}

COACH'S PLAYER OBSERVATION
--------------------------

{coach_observation}

TEAM OBSERVATION
----------------

{team_notes_text}

MATCH INFORMATION
-----------------

Goals:
{goals}

Yellow Cards:
{yellow_cards}

Red Cards:
{red_cards}

Minutes Played:
{minutes_played}

Substitution Information:
{substitution_text}

OUTPUT FORMAT
-------------

PLAYER:
<player name>

POSITION:
<position>

SESSION CONTEXT:
<short context based only on the supplied information>

TECHNICAL

Strengths:
- ...

Areas to Improve:
- ...

TACTICAL

Strengths:
- ...

Areas to Improve:
- ...

PHYSICAL

Strengths:
- ...

Areas to Improve:
- ...

MENTAL / GAME UNDERSTANDING

Strengths:
- ...

Areas to Improve:
- ...

OVERALL STRENGTHS
- ...

PRIORITY AREAS TO IMPROVE
1. ...
2. ...
3. ...

SUGGESTED DRILLS
1. Drill:
   Purpose:
   Coaching Point:

2. Drill:
   Purpose:
   Coaching Point:

NEXT WEEK TRAINING FOCUS
<short practical training focus>

COACH / PARENT NOTE
<short, clear summary>

Remember:
Do not invent information.
If there is insufficient evidence for a category, write:
"No specific observation provided."
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text


# =========================================================
# TEAM AI SUMMARY
# =========================================================

def generate_team_rollup(
    player_feedback_list,
    team_observation="",
    session_type="Training",
    session_date="",
    opponent=""
):

    if not player_feedback_list:

        return (
            "No individual player feedback is available "
            "for generating the team summary."
        )

    team_notes_text = (
        team_observation.strip()
        if team_observation
        else "No specific team observation provided."
    )

    # -----------------------------------------------------
    # Prepare Individual Feedback
    # -----------------------------------------------------

    player_sections = []

    for feedback in player_feedback_list:

        if isinstance(feedback, dict):

            player_name = _get_value(
                feedback,
                "player_name",
                "Unknown Player"
            )

            position = _get_value(
                feedback,
                "position",
                "Unknown Position"
            )

            feedback_text = _get_value(
                feedback,
                "feedback",
                ""
            )

            player_sections.append(
                f"""
PLAYER:
{player_name}

POSITION:
{position}

INDIVIDUAL AI FEEDBACK:
{feedback_text}
"""
            )

        else:

            player_sections.append(
                str(feedback)
            )

    all_player_feedback = "\n\n".join(
        player_sections
    )

    # -----------------------------------------------------
    # Improved Team Summary Prompt
    # -----------------------------------------------------

    prompt = f"""
You are an expert football academy head coach
and team performance analyst.

Your task is to create a practical WHOLE-TEAM coaching
summary from the supplied information.

The summary will be used by a football coach to plan
the team's next training block.

=========================================================
SOURCE INFORMATION
=========================================================

You have three types of information:

1. Coach's team observation
2. Individual player AI feedback
3. Session and match context

You MUST base your answer only on this information.

=========================================================
STRICT EVIDENCE RULES
=========================================================

1. NEVER invent a team weakness.
2. NEVER invent a player weakness.
3. NEVER invent match events, statistics, abilities,
   injuries, emotions, or tactical problems.
4. A team-level weakness should be identified only when:
   - it is directly stated in the team observation, OR
   - the same or closely related issue appears in multiple
     individual player reports.
5. One player's problem must NOT automatically become
   a team problem.
6. Clearly separate team-wide patterns from individual issues.
7. Mention player names only when the supplied evidence
   clearly supports the issue.
8. Do not make medical or injury diagnoses.
9. Training drills must directly relate to identified
   improvement areas.
10. If evidence is insufficient, explicitly say:
    "No specific observation provided."
11. Do not repeat complete individual player reports.
12. Keep the summary concise enough for practical coaching use.

=========================================================
SESSION INFORMATION
=========================================================

Session Type:
{session_type}

Session Date:
{session_date}

Opponent:
{opponent if opponent else "Not applicable"}

=========================================================
COACH'S TEAM OBSERVATION
=========================================================

{team_notes_text}

=========================================================
INDIVIDUAL PLAYER AI FEEDBACK
=========================================================

{all_player_feedback}

=========================================================
ANALYSIS INSTRUCTIONS
=========================================================

Before producing the final answer:

A. Identify repeated patterns across players.

B. Identify issues directly mentioned by the coach.

C. Separate:
   - Common team weaknesses
   - Individual issues
   - Team strengths

D. Give priority to issues that:
   - appear multiple times,
   - are explicitly mentioned by the coach,
   - or have clear relevance to the next training block.

E. Do not create a pattern simply because two words
   happen to be similar. The underlying football issue
   must be meaningfully related.

F. Training priorities should be actionable and realistic
   for a football training session.

=========================================================
OUTPUT FORMAT
=========================================================

TEAM AI SUMMARY

SESSION OVERVIEW
<2-4 sentence summary of the session based only
on the supplied information.>


TEAM STRENGTHS
- <supported team strength>
- <supported team strength>

If no team strength is supported:
"No specific observation provided."


COMMON TEAM WEAKNESSES
- <team-level weakness supported by multiple pieces of evidence>
- <team-level weakness supported by evidence>

If no common team weakness is supported:
"No common weakness clearly identified."


PLAYERS AFFECTED
- <player name> — <specific supported issue>
- <player name> — <specific supported issue>

Only include players where the evidence clearly supports
the issue.

If no individual issue is clearly supported:
"No specific individual issue identified."


TECHNICAL TEAM PATTERNS
- <supported technical pattern>

If insufficient evidence:
"No specific observation provided."


TACTICAL TEAM PATTERNS
- <supported tactical pattern>

If insufficient evidence:
"No specific observation provided."


PHYSICAL TEAM PATTERNS
- <supported physical pattern>

If insufficient evidence:
"No specific observation provided."


MENTAL / GAME UNDERSTANDING PATTERNS
- <supported pattern>

If insufficient evidence:
"No specific observation provided."


MAIN TEAM TRAINING PRIORITIES

1. <highest-priority supported area>
   Reason: <short evidence-based reason>

2. <second priority>
   Reason: <short evidence-based reason>

3. <third priority>
   Reason: <short evidence-based reason>


SUGGESTED TEAM DRILLS

1. Drill:
   Purpose:
   Coaching Points:

2. Drill:
   Purpose:
   Coaching Points:

3. Drill:
   Purpose:
   Coaching Points:


NEXT WEEK TEAM TRAINING FOCUS
<short practical description of what the team should
focus on during the next training block>


WEEKLY COACH SUMMARY
<3-5 sentence practical summary for the coach>


=========================================================
FINAL REMINDER
=========================================================

The output must remain evidence-based.

Do not invent information.

Do not turn an isolated player issue into a team-wide issue.

If there is insufficient evidence for a category, write:
"No specific observation provided."
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text