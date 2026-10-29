import os
import json
import re
import sqlite3
import httpx

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


AI_URL = os.getenv(
    "AI_URL",
    "https://api.groq.com/openai/v1/chat/completions"
)

AI_KEY = os.getenv("AI_KEY")

AI_MODEL = os.getenv(
    "AI_MODEL",
    "openai/gpt-oss-120b"
)


# ============================================================
# CONFIGURATION
# ============================================================

def check_config():

    if not AI_KEY:
        raise Exception(
            "AI_KEY is missing. Add your Groq API key to backend/.env"
        )

    if not AI_URL:
        raise Exception(
            "AI_URL is missing."
        )

    if not AI_MODEL:
        raise Exception(
            "AI_MODEL is missing."
        )


# ============================================================
# JSON EXTRACTION
# ============================================================

def parse_json(text):

    if not text:
        raise ValueError(
            "AI returned an empty response."
        )

    text = str(text).strip()

    # --------------------------------------------------------
    # Remove markdown fences
    # --------------------------------------------------------

    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```",
        "",
        text
    )

    text = text.strip()

    # --------------------------------------------------------
    # Try complete response directly
    # --------------------------------------------------------

    try:

        result = json.loads(text)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Locate first JSON object
    # --------------------------------------------------------

    start = text.find("{")

    if start == -1:

        raise ValueError(
            "AI did not return a JSON object."
        )

    depth = 0
    in_string = False
    escaped = False

    # --------------------------------------------------------
    # Find matching closing brace
    # --------------------------------------------------------

    for i in range(start, len(text)):

        char = text[i]

        if in_string:

            if escaped:

                escaped = False

            elif char == "\\":

                escaped = True

            elif char == '"':

                in_string = False

            continue

        if char == '"':

            in_string = True

        elif char == "{":

            depth += 1

        elif char == "}":

            depth -= 1

            if depth == 0:

                candidate = text[
                    start:i + 1
                ]

                try:

                    result = json.loads(
                        candidate
                    )

                    if isinstance(
                        result,
                        dict
                    ):

                        return result

                except json.JSONDecodeError:

                    raise ValueError(
                        "AI returned malformed JSON."
                    )

    raise ValueError(
        "Incomplete JSON object returned by AI."
    )


# ============================================================
# EXTRACT MESSAGE CONTENT
# ============================================================

def extract_message_content(data):

    choices = data.get(
        "choices",
        []
    )

    if not choices:

        raise Exception(
            "Groq returned no choices."
        )

    message = choices[0].get(
        "message",
        {}
    )

    content = message.get(
        "content"
    )

    # Some reasoning models expose reasoning separately.
    reasoning = message.get(
        "reasoning"
    )

    if content:

        return str(
            content
        ).strip()

    # --------------------------------------------------------
    # Some responses can contain content in a different form
    # --------------------------------------------------------

    if isinstance(
        content,
        list
    ):

        parts = []

        for item in content:

            if isinstance(
                item,
                dict
            ):

                value = item.get(
                    "text"
                )

                if value:

                    parts.append(
                        str(value)
                    )

        if parts:

            return "\n".join(
                parts
            ).strip()

    # --------------------------------------------------------
    # Helpful debugging
    # --------------------------------------------------------

    print()
    print("========== EMPTY AI CONTENT ==========")
    print(
        json.dumps(
            data,
            indent=2
        )[:7000]
    )
    print("======================================")
    print()

    if reasoning:

        raise Exception(
            "Groq returned reasoning but no final content."
        )

    raise Exception(
        "Groq returned empty content."
    )


# ============================================================
# RAW GROQ REQUEST
# ============================================================

async def raw_ai_request(
    prompt,
    max_tokens=1600
):

    check_config()

    headers = {
        "Authorization": f"Bearer {AI_KEY}",
        "Content-Type": "application/json"
    }

    system_message = """
You are an expert software architect.

Your task is to generate structured JSON for an
AI-powered Software Development Lifecycle assistant.

IMPORTANT:
Return ONLY one valid JSON object.

Rules:
- No markdown.
- No ```json.
- No explanation.
- No comments.
- No text before JSON.
- No text after JSON.
- Never return an array as the root.
- Complete the JSON object before stopping.
- Keep descriptions concise.
- Follow the requested schema exactly.
"""

    body = {
        "model": AI_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        "temperature": 0,

        "max_tokens": max_tokens,

        # Important for GPT-OSS reasoning models.
        "reasoning_effort": "low",

        "reasoning_format": "hidden"
    }

    print()
    print("========================================")
    print("CALLING GROQ")
    print("========================================")
    print("Model:", AI_MODEL)
    print("Max tokens:", max_tokens)
    print("========================================")
    print()

    try:

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.post(
                AI_URL,
                headers=headers,
                json=body
            )

    except httpx.TimeoutException:

        raise Exception(
            "Groq request timed out after 180 seconds."
        )

    except httpx.RequestError as error:

        raise Exception(
            f"Could not connect to Groq: {error}"
        )

    # ========================================================
    # HTTP ERROR
    # ========================================================

    if response.status_code != 200:

        print()
        print("========== GROQ HTTP ERROR ==========")
        print("Status:", response.status_code)
        print(response.text[:5000])
        print("=====================================")
        print()

        raise Exception(
            f"Groq API returned "
            f"{response.status_code}: "
            f"{response.text[:1500]}"
        )

    # ========================================================
    # PARSE HTTP JSON
    # ========================================================

    try:

        data = response.json()

    except Exception:

        raise Exception(
            "Groq returned invalid HTTP JSON."
        )

    # ========================================================
    # GET CONTENT
    # ========================================================

    content = extract_message_content(
        data
    )

    if not content:

        raise Exception(
            "Groq returned empty content."
        )

    print()
    print("========== AI OUTPUT ==========")
    print(content[:5000])
    print("================================")
    print()

    return content


# ============================================================
# GROQ CALL + JSON PARSING + RETRY
# ============================================================

async def call_ai(
    prompt,
    max_tokens=1600
):

    # --------------------------------------------------------
    # First attempt
    # --------------------------------------------------------

    try:

        content = await raw_ai_request(
            prompt,
            max_tokens
        )

        result = parse_json(
            content
        )

        return result

    except Exception as first_error:

        print()
        print("========================================")
        print("FIRST AI ATTEMPT FAILED")
        print("========================================")
        print(str(first_error))
        print("========================================")
        print()

    # --------------------------------------------------------
    # Compact retry
    # --------------------------------------------------------

    retry_prompt = f"""
Generate the requested result again.

This time follow these rules VERY strictly:

1. Return ONLY one JSON object.
2. Do not use markdown.
3. Do not use ```json.
4. Do not explain anything.
5. Do not add extra fields.
6. Keep every text value short.
7. Keep arrays within the requested limits.
8. Make sure the JSON is COMPLETE.
9. Do not stop before the closing }}.

Original request:

{prompt}
"""

    try:

        retry_content = await raw_ai_request(
            retry_prompt,
            min(
                max_tokens,
                1400
            )
        )

        result = parse_json(
            retry_content
        )

        return result

    except Exception as retry_error:

        print()
        print("========================================")
        print("RETRY FAILED")
        print("========================================")
        print(str(retry_error))
        print("========================================")
        print()

        raise Exception(
            "AI JSON generation failed. "
            f"First error: {first_error}. "
            f"Retry error: {retry_error}"
        )


# ============================================================
# 1. REQUIREMENT ANALYZER
# ============================================================

# ============================================================
# 1. REQUIREMENT ANALYZER
# ============================================================

async def generate_requirements(requirements):

    prompt = f"""
You are analyzing software requirements for an SDLC assistant.

PROJECT REQUIREMENTS:
{requirements}

Your job is to identify the actual requirements, system actors,
and use cases directly from the project description.

Return EXACTLY this JSON structure:

{{
  "project": {{
    "name": "Project name",
    "summary": "Short project summary",
    "domain": "Application domain"
  }},

  "functional_requirements": [
    "Functional requirement 1",
    "Functional requirement 2"
  ],

  "non_functional_requirements": [
    "Non-functional requirement 1",
    "Non-functional requirement 2"
  ],

  "actors": [
    {{
      "name": "Actor name",
      "description": "What this actor does in the system"
    }}
  ],

  "use_cases": [
    {{
      "name": "Use case name",
      "actor": "Actor name",
      "description": "What the actor does in this use case"
    }}
  ],

  "acceptance_criteria": [
    {{
      "requirement": "Related requirement",
      "criteria": [
        "Acceptance criterion 1",
        "Acceptance criterion 2"
      ]
    }}
  ],

  "clarifications": []
}}

STRICT REQUIREMENT ANALYSIS RULES:

1. Generate EXACTLY 5 functional requirements.
2. Generate EXACTLY 4 non-functional requirements.
3. Generate EXACTLY 3 system actors.
4. Generate EXACTLY 5 use cases.
5. Every actor MUST have:
   - name
   - description

6. Every use case MUST have:
   - name
   - actor
   - description

7. The actor field of every use case MUST exactly match
   one of the generated actor names.

8. Actors must be real users, administrators, external systems,
   services, or other entities that actually interact with
   the software.

9. Do NOT use generic actors such as:
   - System
   - Application
   - Software
   - Database

10. Use cases must represent actual actions performed by actors.

11. Do NOT return empty actors.

12. Do NOT return empty use_cases.

13. Generate actors and use cases specifically from the supplied
    project requirements. Do not invent unrelated functionality.

14. Generate EXACTLY 5 acceptance-criteria objects.

15. Each acceptance-criteria object must contain:
   - requirement
   - criteria

16. Each criteria array should contain 2 concise criteria.

17. Put genuinely unclear requirements in clarifications.
    If everything is clear, return an empty array.

18. Return ONLY valid JSON.
19. Do NOT use markdown.
20. Do NOT use ```json.
21. Do NOT include explanations outside the JSON.
22. Do NOT add extra fields.
23. Complete the JSON before stopping.

Before returning the answer, verify:

- actors contains exactly 3 objects
- use_cases contains exactly 5 objects
- every actor has name and description
- every use case has name, actor and description
- every use case actor matches an actor name
"""

    result = await call_ai(
        prompt,
        1800
    )

    # --------------------------------------------------------
    # Safety validation
    # --------------------------------------------------------

    actors = result.get("actors", [])
    use_cases = result.get("use_cases", [])

    if not isinstance(actors, list):
        actors = []

    if not isinstance(use_cases, list):
        use_cases = []

    # Remove malformed actors
    actors = [
        actor for actor in actors
        if isinstance(actor, dict)
        and str(actor.get("name", "")).strip()
        and str(actor.get("description", "")).strip()
    ]

    # Remove malformed use cases
    use_cases = [
        use_case for use_case in use_cases
        if isinstance(use_case, dict)
        and str(use_case.get("name", "")).strip()
        and str(use_case.get("actor", "")).strip()
        and str(use_case.get("description", "")).strip()
    ]

    # --------------------------------------------------------
    # If AI failed to generate them correctly, make a dedicated
    # smaller AI request instead of allowing empty output.
    # --------------------------------------------------------

    if len(actors) < 3 or len(use_cases) < 5:

        repair_prompt = f"""
Analyze these software requirements:

{requirements}

Generate ONLY this JSON:

{{
  "actors": [
    {{
      "name": "",
      "description": ""
    }}
  ],
  "use_cases": [
    {{
      "name": "",
      "actor": "",
      "description": ""
    }}
  ]
}}

Rules:

- EXACTLY 3 actors.
- EXACTLY 5 use cases.
- Every actor needs name and description.
- Every use case needs name, actor and description.
- The actor in a use case MUST exactly match one of the actor names.
- Actors must actually interact with the software.
- Use cases must be actual actions.
- Do not use "System", "Application", "Software", or "Database"
  as actors.
- Do not invent unrelated features.
- Return ONLY JSON.
"""

        repaired = await call_ai(
            repair_prompt,
            900
        )

        repaired_actors = repaired.get("actors", [])
        repaired_use_cases = repaired.get("use_cases", [])

        if isinstance(repaired_actors, list):
            repaired_actors = [
                actor for actor in repaired_actors
                if isinstance(actor, dict)
                and str(actor.get("name", "")).strip()
                and str(actor.get("description", "")).strip()
            ]

        if isinstance(repaired_use_cases, list):
            repaired_use_cases = [
                use_case for use_case in repaired_use_cases
                if isinstance(use_case, dict)
                and str(use_case.get("name", "")).strip()
                and str(use_case.get("actor", "")).strip()
                and str(use_case.get("description", "")).strip()
            ]

        if len(repaired_actors) >= 3:
            actors = repaired_actors[:3]

        if len(repaired_use_cases) >= 5:
            use_cases = repaired_use_cases[:5]

    # --------------------------------------------------------
    # Final normalization
    # --------------------------------------------------------

    result["actors"] = actors[:3]
    result["use_cases"] = use_cases[:5]

    # Make sure these fields ALWAYS exist
    result.setdefault("functional_requirements", [])
    result.setdefault("non_functional_requirements", [])
    result.setdefault("acceptance_criteria", [])
    result.setdefault("clarifications", [])

    return result

    # ============================================================
# 2. USER STORY GENERATOR
# ============================================================

async def generate_user_stories(requirements):

    prompt = f"""
Create Agile user stories for the following software project:

{requirements}

Return exactly this JSON structure:

{{
  "user_stories": [
    {{
      "id": "US-001",
      "story": "As a [user], I want [action], so that [benefit].",
      "priority": "High",
      "story_points": 3,
      "sprint": "Sprint 1",
      "acceptance_criteria": [
        "Acceptance criterion 1",
        "Acceptance criterion 2"
      ]
    }}
  ]
}}

Rules:

1. Generate EXACTLY 6 user stories.
2. IDs must be US-001 through US-006.
3. Every story must follow:
   As a [user], I want [action], so that [benefit].
4. Priority must be exactly one of:
   High, Medium, Low
5. Story points must be exactly one of:
   1, 2, 3, 5, 8
6. Sprint must be:
   Sprint 1, Sprint 2, or Sprint 3.
7. Generate EXACTLY 2 acceptance criteria for every story.
8. Stories must be based directly on the supplied requirements.
9. Do not invent unrelated functionality.
10. Keep stories concise.
11. Return ONLY valid JSON.
12. Do not use markdown.
13. Do not use ```json.
14. Do not add explanations.
"""

    result = await call_ai(
        prompt,
        1500
    )

    # --------------------------------------------------------
    # Validate generated stories
    # --------------------------------------------------------

    stories = result.get("user_stories", [])

    if not isinstance(stories, list):
        stories = []

    valid_stories = []

    for index, story in enumerate(stories):

        if not isinstance(story, dict):
            continue

        story_id = str(
            story.get("id", "")
        ).strip()

        story_text = str(
            story.get("story", "")
        ).strip()

        priority = str(
            story.get("priority", "Medium")
        ).strip()

        sprint = str(
            story.get("sprint", "Sprint 1")
        ).strip()

        criteria = story.get(
            "acceptance_criteria",
            []
        )

        if not story_id:
            story_id = f"US-{index + 1:03d}"

        if not story_text:
            continue

        if priority not in {
            "High",
            "Medium",
            "Low"
        }:
            priority = "Medium"

        if sprint not in {
            "Sprint 1",
            "Sprint 2",
            "Sprint 3"
        }:
            sprint = "Sprint 1"

        if not isinstance(criteria, list):
            criteria = []

        criteria = [
            str(item).strip()
            for item in criteria
            if str(item).strip()
        ]

        valid_stories.append({
            "id": story_id,
            "story": story_text,
            "priority": priority,
            "story_points": story.get(
                "story_points",
                3
            ),
            "sprint": sprint,
            "acceptance_criteria": criteria[:2]
        })

    # --------------------------------------------------------
    # If AI returned nothing, retry with a smaller prompt
    # --------------------------------------------------------

    if len(valid_stories) < 6:

        retry_prompt = f"""
Generate exactly 6 Agile user stories from these requirements:

{requirements}

Return ONLY:

{{
  "user_stories": [
    {{
      "id": "US-001",
      "story": "As a user, I want to ... so that ...",
      "priority": "High",
      "story_points": 3,
      "sprint": "Sprint 1",
      "acceptance_criteria": [
        "...",
        "..."
      ]
    }}
  ]
}}

Rules:
- Exactly 6 stories.
- IDs US-001 to US-006.
- Exactly 2 acceptance criteria each.
- Priority: High, Medium, or Low.
- Story points: 1, 2, 3, 5, or 8.
- Sprint: Sprint 1, Sprint 2, or Sprint 3.
- Use only features from the requirements.
- Return valid JSON only.
"""

        retry_result = await call_ai(
            retry_prompt,
            1300
        )

        retry_stories = retry_result.get(
            "user_stories",
            []
        )

        if isinstance(retry_stories, list):

            for index, story in enumerate(
                retry_stories[:6]
            ):

                if not isinstance(
                    story,
                    dict
                ):
                    continue

                story_text = str(
                    story.get(
                        "story",
                        ""
                    )
                ).strip()

                if not story_text:
                    continue

                valid_stories.append({
                    "id": f"US-{index + 1:03d}",
                    "story": story_text,
                    "priority": story.get(
                        "priority",
                        "Medium"
                    ),
                    "story_points": story.get(
                        "story_points",
                        3
                    ),
                    "sprint": story.get(
                        "sprint",
                        "Sprint 1"
                    ),
                    "acceptance_criteria":
                        story.get(
                            "acceptance_criteria",
                            []
                        )[:2]
                })

    return {
        "user_stories": valid_stories[:6]
    }
# ============================================================
# 3. UML GENERATOR
# ============================================================

async def generate_uml(
    requirements
):

    prompt = f"""
Create compact UML diagrams for:

{requirements}

Return exactly:

{{
  "use_case": "",
  "class_diagram": "",
  "sequence": ""
}}

Rules:

- Use Mermaid syntax.
- use_case must start with "flowchart LR".
- class_diagram must start with "classDiagram".
- sequence must start with "sequenceDiagram".
- Maximum 6 classes.
- Maximum 8 relationships.
- Keep diagrams compact.
- Do not use markdown fences.
- Do not put explanations inside the Mermaid diagrams.
"""

    return await call_ai(
        prompt,
        1800
    )


# ============================================================
# 4. DATABASE DESIGNER
# ============================================================

async def generate_database(
    requirements
):

    prompt = f"""
Design a relational database for:

{requirements}

Return exactly:

{{
  "tables": [
    {{
      "table": "",
      "columns": [
        {{
          "name": "",
          "type": "INTEGER",
          "primary_key": false,
          "foreign_key": false,
          "references": ""
        }}
      ]
    }}
  ],
  "relationships": [
    {{
      "from": "",
      "to": "",
      "cardinality": "1:N",
      "description": ""
    }}
  ]
}}

Rules:

- Exactly 4 tables.
- Each table must contain 4 to 6 columns.
- Every table must have exactly one INTEGER primary key.
- Allowed types:
  INTEGER
  TEXT
  REAL
  BOOLEAN
  DATETIME
- Foreign key references must use:
  table.column
- Use realistic relational design.
- Do not generate SQL.
- Do not generate Mermaid.
- Keep descriptions short.
"""

    return await call_ai(
        prompt,
        1800
    )


# ============================================================
# DATABASE IDENTIFIER SANITIZATION
# ============================================================

def safe_identifier(
    value,
    fallback
):

    value = str(
        value or ""
    ).strip()

    value = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        value
    )

    if not value:

        value = fallback

    if value[0].isdigit():

        value = "_" + value

    return value


# ============================================================
# DATABASE SQL BUILDER
# ============================================================

def build_database_sql(
    database
):

    tables = database.get(
        "tables",
        []
    )

    statements = []

    for table_index, table in enumerate(
        tables
    ):

        raw_table_name = table.get(
            "table",
            ""
        )

        table_name = safe_identifier(
            raw_table_name,
            f"table_{table_index + 1}"
        )

        columns = []

        foreign_keys = []

        for column_index, column in enumerate(
            table.get(
                "columns",
                []
            )
        ):

            raw_name = column.get(
                "name",
                ""
            )

            name = safe_identifier(
                raw_name,
                f"column_{column_index + 1}"
            )

            column_type = str(
                column.get(
                    "type",
                    "TEXT"
                )
            ).upper().strip()

            allowed_types = {
                "INTEGER",
                "TEXT",
                "REAL",
                "BOOLEAN",
                "DATETIME"
            }

            if column_type not in allowed_types:

                column_type = "TEXT"

            definition = (
                f"{name} {column_type}"
            )

            if column.get(
                "primary_key",
                False
            ):

                if column_type == "INTEGER":

                    definition += (
                        " PRIMARY KEY AUTOINCREMENT"
                    )

                else:

                    definition += (
                        " PRIMARY KEY"
                    )

            columns.append(
                definition
            )

            # ------------------------------------------------
            # Foreign key
            # ------------------------------------------------

            if column.get(
                "foreign_key",
                False
            ):

                reference = str(
                    column.get(
                        "references",
                        ""
                    )
                ).strip()

                if "." in reference:

                    ref_table, ref_column = (
                        reference.split(
                            ".",
                            1
                        )
                    )

                    ref_table = safe_identifier(
                        ref_table,
                        "unknown_table"
                    )

                    ref_column = safe_identifier(
                        ref_column,
                        "id"
                    )

                    foreign_keys.append(
                        f"FOREIGN KEY ({name}) "
                        f"REFERENCES "
                        f"{ref_table}({ref_column})"
                    )

        columns.extend(
            foreign_keys
        )

        if not columns:

            columns.append(
                "id INTEGER PRIMARY KEY AUTOINCREMENT"
            )

        statement = (
            f"CREATE TABLE {table_name} (\n"
            +
            ",\n".join(
                f"    {column}"
                for column in columns
            )
            +
            "\n);"
        )

        statements.append(
            statement
        )

    return "\n\n".join(
        statements
    )


# ============================================================
# ER DIAGRAM
# ============================================================

def build_er_diagram(
    database
):

    lines = [
        "erDiagram"
    ]

    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------

    for relationship in database.get(
        "relationships",
        []
    ):

        source = safe_identifier(
            relationship.get(
                "from",
                ""
            ),
            ""
        ).upper()

        target = safe_identifier(
            relationship.get(
                "to",
                ""
            ),
            ""
        ).upper()

        if not source or not target:

            continue

        cardinality = str(
            relationship.get(
                "cardinality",
                "1:N"
            )
        ).upper().strip()

        description = str(
            relationship.get(
                "description",
                "related"
            )
        ).strip()

        description = re.sub(
            r"[^A-Za-z0-9_ -]",
            "",
            description
        )

        if not description:

            description = "related"

        if cardinality == "1:1":

            lines.append(
                f"{source} ||--|| {target} : {description}"
            )

        elif cardinality in {
            "N:M",
            "M:N"
        }:

            lines.append(
                f"{source} }}o--o{{ {target} : {description}"
            )

        else:

            lines.append(
                f"{source} ||--o{{ {target} : {description}"
            )

    # --------------------------------------------------------
    # Tables
    # --------------------------------------------------------

    for table_index, table in enumerate(
        database.get(
            "tables",
            []
        )
    ):

        name = safe_identifier(
            table.get(
                "table",
                ""
            ),
            f"table_{table_index + 1}"
        ).upper()

        lines.append(
            f"{name} {{"
        )

        for column in table.get(
            "columns",
            []
        ):

            column_name = safe_identifier(
                column.get(
                    "name",
                    ""
                ),
                "column"
            )

            column_type = str(
                column.get(
                    "type",
                    "TEXT"
                )
            ).lower()

            marker = ""

            if column.get(
                "primary_key",
                False
            ):

                marker = " PK"

            elif column.get(
                "foreign_key",
                False
            ):

                marker = " FK"

            lines.append(
                f"    {column_type} "
                f"{column_name}{marker}"
            )

        lines.append(
            "}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# 5. API DESIGNER
# ============================================================

async def generate_apis(
    requirements
):

    prompt = f"""
Design REST APIs for:

{requirements}

Return exactly:

{{
  "apis": [
    {{
      "method": "GET",
      "endpoint": "/api/example",
      "purpose": "",
      "request_body": {{}},
      "response_body": {{}},
      "status_codes": [
        {{
          "code": 200,
          "description": ""
        }}
      ]
    }}
  ]
}}

Rules:

- Exactly 6 APIs.
- Use GET, POST, PUT, PATCH, or DELETE where appropriate.
- Every endpoint must be realistic.
- Keep request bodies small.
- Keep response bodies small.
- Maximum 2 status codes per API.
- Use valid JSON objects for request_body and response_body.
"""

    return await call_ai(
        prompt,
        1900
    )


# ============================================================
# 6. PROJECT STRUCTURE
# ============================================================

async def generate_structure(
    requirements
):

    prompt = f"""
Design the software architecture for:

{requirements}

Return exactly:

{{
  "technology_stack": [
    {{
      "category": "",
      "technology": ""
    }}
  ],
  "architecture": "",
  "dependencies": [],
  "folders": [],
  "architecture_diagram": ""
}}

Rules:

- Frontend must use React + Vite.
- Backend must use FastAPI.
- Database must be relational.
- Maximum 8 technology stack entries.
- Maximum 8 dependencies.
- Maximum 8 folders.
- architecture_diagram must use Mermaid.
- architecture_diagram must start with "flowchart TD".
- Keep everything concise.
"""

    return await call_ai(
        prompt,
        1500
    )


# ============================================================
# 7. DOCUMENTATION
# ============================================================

async def generate_documentation(
    requirements
):

    prompt = f"""
Create concise project documentation for:

{requirements}

Return exactly:

{{
  "readme": "",
  "api_documentation": "",
  "installation": "",
  "deployment": "",
  "sprint_plan": "",
  "architecture": ""
}}

Rules:

- Each value must be under 100 words.
- Keep everything practical.
- Do not use markdown code fences.
- Do not invent technologies that are not required.
"""

    return await call_ai(
        prompt,
        1600
    )


# ============================================================
# DATABASE VALIDATION
# ============================================================

def validate_database(
    database
):

    sql = database.get(
        "sql",
        ""
    )

    if not sql:

        database["validation"] = {
            "sql_syntax": "Not generated",
            "semantic": "Not checked"
        }

        return

    connection = None

    try:

        connection = sqlite3.connect(
            ":memory:"
        )

        cursor = connection.cursor()

        cursor.execute(
            "PRAGMA foreign_keys = ON"
        )

        statements = [
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        ]

        for statement in statements:

            cursor.execute(
                statement
            )

        # ----------------------------------------------------
        # Check generated tables
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """
        )

        created_tables = {
            row[0]
            for row in cursor.fetchall()
        }

        expected_tables = {
            safe_identifier(
                table.get(
                    "table",
                    ""
                ),
                ""
            )
            for table in database.get(
                "tables",
                []
            )
        }

        expected_tables.discard("")

        if expected_tables.issubset(
            created_tables
        ):

            semantic_status = "Valid"

        else:

            semantic_status = (
                "Warning: Some tables were not created."
            )

        syntax_status = "Valid"

    except Exception as error:

        syntax_status = (
            f"Warning: {error}"
        )

        semantic_status = (
            "Not checked"
        )

    finally:

        if connection:

            connection.close()

    database["validation"] = {
        "sql_syntax": syntax_status,
        "semantic": semantic_status
    }


# ============================================================
# NORMALIZE RESULT
# ============================================================

def normalize_result(
    requirement_data,
    story_data,
    uml_data,
    database_data,
    api_data,
    structure_data,
    documentation_data
):

    return {

        "project": requirement_data.get(
            "project",
            {}
        ),

        "requirement_analysis": {

            "functional_requirements":
                requirement_data.get(
                    "functional_requirements",
                    []
                ),

            "non_functional_requirements":
                requirement_data.get(
                    "non_functional_requirements",
                    []
                ),

            "actors":
                requirement_data.get(
                    "actors",
                    []
                ),

            "use_cases":
                requirement_data.get(
                    "use_cases",
                    []
                ),

            "acceptance_criteria":
                requirement_data.get(
                    "acceptance_criteria",
                    []
                ),

            "clarifications":
                requirement_data.get(
                    "clarifications",
                    []
                )
        },

        "user_stories":
            story_data.get(
                "user_stories",
                []
            ),

        "uml": {

            "use_case":
                uml_data.get(
                    "use_case",
                    ""
                ),

            "class_diagram":
                uml_data.get(
                    "class_diagram",
                    ""
                ),

            "sequence":
                uml_data.get(
                    "sequence",
                    ""
                )
        },

        "database":
            database_data,

        "apis":
            api_data.get(
                "apis",
                []
            ),

        "project_structure":
            structure_data,

        "documentation":
            documentation_data,

        "review": {

            "needs_clarification": bool(
                requirement_data.get(
                    "clarifications",
                    []
                )
            ),

            "questions":
                requirement_data.get(
                    "clarifications",
                    []
                )
        }
    }


# ============================================================
# FINAL RESULT VALIDATION
# ============================================================

def validate_result(
    result
):

    required_fields = [
        "project",
        "requirement_analysis",
        "user_stories",
        "uml",
        "database",
        "apis",
        "project_structure",
        "documentation",
        "review"
    ]

    for field in required_fields:

        if field not in result:

            raise Exception(
                f"Missing result field: {field}"
            )

    # --------------------------------------------------------
    # Basic structure checks
    # --------------------------------------------------------

    if not isinstance(
        result["project"],
        dict
    ):

        raise Exception(
            "Invalid project result."
        )

    if not isinstance(
        result["requirement_analysis"],
        dict
    ):

        raise Exception(
            "Invalid requirement analysis result."
        )

    if not isinstance(
        result["user_stories"],
        list
    ):

        raise Exception(
            "Invalid user stories result."
        )

    if not isinstance(
        result["uml"],
        dict
    ):

        raise Exception(
            "Invalid UML result."
        )

    if not isinstance(
        result["database"],
        dict
    ):

        raise Exception(
            "Invalid database result."
        )

    if not isinstance(
        result["apis"],
        list
    ):

        raise Exception(
            "Invalid API result."
        )


# ============================================================
# MAIN SDLC GENERATOR
# ============================================================

async def generate_sdlc(
    requirements
):

    requirements = (
        requirements or ""
    ).strip()

    if not requirements:

        raise Exception(
            "Requirements cannot be empty."
        )

    print()
    print("========================================")
    print("AI SDLC GENERATION STARTED")
    print("========================================")
    print()

    # ========================================================
    # 1. REQUIREMENT ANALYSIS
    # ========================================================

    print(
        "1/7 Requirement Analyzer..."
    )

    requirement_data = (
        await generate_requirements(
            requirements
        )
    )

    # ========================================================
    # 2. USER STORIES
    # ========================================================

    print(
        "2/7 User Story Generator..."
    )

    story_data = (
        await generate_user_stories(
            requirements
        )
    )

    # ========================================================
    # 3. UML
    # ========================================================

    print(
        "3/7 UML Generator..."
    )

    uml_data = (
        await generate_uml(
            requirements
        )
    )

    # ========================================================
    # 4. DATABASE
    # ========================================================

    print(
        "4/7 Database Designer..."
    )

    database_data = (
        await generate_database(
            requirements
        )
    )

    # --------------------------------------------------------
    # Build SQL locally
    # --------------------------------------------------------

    database_data["sql"] = (
        build_database_sql(
            database_data
        )
    )

    # --------------------------------------------------------
    # Build ER diagram locally
    # --------------------------------------------------------

    database_data["er_diagram"] = (
        build_er_diagram(
            database_data
        )
    )

    # --------------------------------------------------------
    # Validate SQL
    # --------------------------------------------------------

    validate_database(
        database_data
    )

    # ========================================================
    # 5. API DESIGN
    # ========================================================

    print(
        "5/7 API Designer..."
    )

    api_data = (
        await generate_apis(
            requirements
        )
    )

    # ========================================================
    # 6. PROJECT STRUCTURE
    # ========================================================

    print(
        "6/7 Project Structure..."
    )

    structure_data = (
        await generate_structure(
            requirements
        )
    )

    # ========================================================
    # 7. DOCUMENTATION
    # ========================================================

    print(
        "7/7 Documentation..."
    )

    documentation_data = (
        await generate_documentation(
            requirements
        )
    )

    # ========================================================
    # COMBINE EVERYTHING
    # ========================================================

    result = normalize_result(
        requirement_data,
        story_data,
        uml_data,
        database_data,
        api_data,
        structure_data,
        documentation_data
    )

    # ========================================================
    # VALIDATE FINAL RESULT
    # ========================================================

    validate_result(
        result
    )

    # ========================================================
    # FINAL LOG
    # ========================================================

    print()
    print("========================================")
    print("AI SDLC GENERATION COMPLETE")
    print("========================================")
    print()

    print(
        "Generated:"
    )

    print(
        "✓ Requirement Analysis"
    )

    print(
        "✓ User Stories"
    )

    print(
        "✓ UML Diagrams"
    )

    print(
        "✓ Database Schema"
    )

    print(
        "✓ SQL"
    )

    print(
        "✓ ER Diagram"
    )

    print(
        "✓ REST APIs"
    )

    print(
        "✓ Project Structure"
    )

    print(
        "✓ Documentation"
    )

    print()

    return result