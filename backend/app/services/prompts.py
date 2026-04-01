from __future__ import annotations

"""
Coaching analysis prompt templates.

This is the most important file in the entire application.
The prompt defines HOW Claude analyzes teaching — it IS the product logic.

Synthesized from three sources (2026-04-01):
1. Local prompts.py (JSON output, 4-dimension framework)
2. GitHub prompts.py (Chaos-6/adult-learning-coach, plain-text output,
   operational definitions, strict formatting)
3. Coaching-Prompt_v4.md (most sophisticated rubric: operational definitions,
   transparency requirements, VERIFIED/ESTIMATED labels, 9-section output)

Key design decisions:
1. System prompt sets the role, persona, and constraints
2. Operational definitions ensure reproducible, consistent counts
3. Analysis instructions define 4 dimensions with specific metrics
4. Output format is structured JSON — eliminates markdown parsing fragility
5. Sampling strategy ensures balanced evidence across the full session
6. 2:1 strength-to-improvement ratio keeps feedback motivational
7. Confidence labeling + shown calculations provide metric transparency
8. Every JSON field maps directly to a PDF section — no missing sections

Comparison prompts (multi-video analysis):
- Each comparison type has its own prompt builder function
- All three share COMPARISON_SYSTEM_PROMPT for the coach persona
- Input: evaluation report summaries (NOT raw transcripts) to stay in token budget
- Three types: personal_performance, class_delivery, program_evaluation
"""


SYSTEM_PROMPT = """You are an expert instructional coach specializing in adult \
learning and professional development for technical subjects. You have 15+ years \
of experience coaching instructors who teach professional development courses to \
adult learners, with deep expertise in helping subject matter experts transition \
into effective teaching.

Your coaching philosophy:
- Growth-oriented: Focus on building strengths, not just fixing weaknesses. \
Assume competence; frame teaching as a new skillset, not a deficit.
- Evidence-based: Every observation is grounded in specific transcript moments \
with timestamps. Use a collaborative tone ("we can explore...", "try...").
- Actionable: Every piece of feedback includes a concrete, immediately \
implementable suggestion. Avoid vague advice like "be more engaging."
- Respectful: You coach the teaching, never judge the person. Focus on \
observable behaviors and transcript evidence, never personality or presumed intent.
- Adult learning aware: You understand andragogy (adult learning theory) and \
connect feedback to established principles. Adult learners are goal-oriented, \
self-directed, experienced, and value relevance and real-world application.

You NEVER use evaluative language like "poor," "bad," "inadequate," or "failing." \
Instead, you frame everything as growth opportunities with specific next steps.

You maintain a minimum 2:1 ratio of strengths to growth areas. Teaching is hard, \
and instructors deserve to hear what's working."""


def build_analysis_prompt(
    transcript: str,
    instructor_name: str = "the instructor",
    class_name: str | None = None,
) -> str:
    """Build the full analysis prompt for Claude.

    This is the core "algorithm" of the product. It instructs Claude to:
    1. Apply strict operational definitions for consistent counting
    2. Divide the transcript into 3 segments for balanced sampling
    3. Analyze 4 dimensions with specific metrics
    4. Extract evidence with timestamps across all segments
    5. Calculate metrics with shown formulas and confidence labels
    6. Generate a structured JSON coaching report

    The output is structured JSON — every key maps directly to a section
    in the PDF report. No markdown parsing, no missing sections.

    Args:
        transcript: The full timestamped transcript text.
        instructor_name: Name of the instructor (for personalization).
        class_name: Name/identifier of the class being taught.

    Returns:
        The complete prompt string to send to Claude.
    """
    class_line = f" — {class_name}" if class_name else ""
    return f"""Analyze the following transcript of a distance learning session \
taught by {instructor_name}{class_line}. Generate a comprehensive coaching report \
following the structure and requirements below exactly.


OPERATIONAL DEFINITIONS

Apply these definitions consistently when counting and labeling behaviors.

Explicit Check for Understanding
Counts as an explicit check ONLY if the instructor:
  1. Asks a direct question to verify comprehension (e.g., "What questions do \
you have?", "Can someone explain how this would apply to your project?").
  2. Waits at least 5 seconds for any response.
  3. Listens to or reads responses before continuing.
Do NOT count: Rhetorical questions ("Right?"), questions not expecting \
substantive response, "Any questions?" followed by immediate continuation, \
"Does that make sense?" without a meaningful wait.
Count separately: checks with responses vs. checks without responses.

Strategic Pause
Counts as a strategic pause ONLY if it:
  1. Is a deliberate silence of 3+ seconds.
  2. Follows a key concept or major idea.
  3. Is used intentionally for processing, emphasis, or invitation and is \
followed by an explicit invitation to reflect, question, or engage.
Do NOT count: Filler pauses while thinking, technical delays (platform issues, \
unmuting), pauses in mid-sentence, pauses under 3 seconds.

Explicit Question
An utterance designed to elicit a learner response (not rhetorical), such as:
  "What would you do differently if...?"
  "Who has experience with...?"
  "What is the main takeaway here?"
  "How does this connect to what you mentioned earlier?"

Significant Tangent
A segment that lasts more than 2 consecutive minutes AND:
  1. Is not in the stated learning objectives.
  2. Does not directly support the current concept.
  3. Is not answering an explicit learner question.
  4. Diverts focus from planned content.
Do NOT count as tangent if: Explicitly framed as optional/advanced, directly \
responsive to learner confusion/request, or used to reinforce conceptual connections.

Curse of Knowledge Indicator
A moment where the instructor:
  1. Uses a technical term without defining or explaining it.
  2. Assumes knowledge of an unintroduced concept.
  3. Skips foundational steps because they feel "obvious."
  4. References prior knowledge not actually introduced in the class.


ANALYSIS FRAMEWORK

Step 1: Segment the Transcript
Divide the transcript into 3 roughly equal segments:
  Segment A (Opening): First third of the session
  Segment B (Middle): Second third
  Segment C (Closing): Final third

Sampling Requirements:
  You MUST extract at least 1 strength example from EACH segment (A, B, C).
  You MUST extract at least 1 growth-opportunity example from EACH segment.
  For each prioritized improvement, provide 3+ timestamped examples drawn \
across segments.
  Label each timestamp with its segment (e.g., "15:30 Segment A").
  After analysis, check for clustering. Re-balance if all examples come from \
a single segment.

Step 2: Analyze Four Dimensions

Dimension 1: Clarity and Pacing
  Speaking Pace (WPM): Total words divided by total minutes. Target: 120-160 WPM. \
Flag if above 160 (very fast) or below 120 (slow). Show calculation.
  Strategic Pauses: Count using the operational definition above. Compute: \
(Total pauses divided by total minutes) times 10 = pauses per 10 minutes. \
Target: 4-6 per 10 minutes. Note segment for each.
  Filler Words: Count "um, uh, like, you know, sort of, basically, literally, \
actually, essentially, right?" per minute. Target: fewer than 3 per minute.
  Jargon / Curse of Knowledge: Flag each instance with timestamp and term. \
Count total instances. Note sentence complexity and helpful vs. redundant repetition.
  Connect observations to adult learners' need for cognitively manageable pacing.

Dimension 2: Engagement Techniques
  Question Frequency: Count explicit questions using the operational definition. \
Compute: (Total questions divided by total minutes) times 5 = questions per \
5 minutes. Target: more than 1 per 5 minutes.
  Question Types: Categorize each question as one of:
    Checking Understanding ("Does that make sense?")
    Inviting Participation ("What has been your experience with...?")
    Rhetorical ("So why does this matter?")
    Probing/Follow-up ("Can you tell me more about...?")
  Explicit Understanding Checks: Count using the operational definition. \
Report checks with response vs. checks without response separately. \
Target: 6-8 per hour.
  Interaction Patterns: Note moments where {instructor_name} responds to \
learner input, builds on learner contributions, or creates discussion.
  Connect engagement patterns to autonomy, relevance, and experience-based learning.

Dimension 3: Explanation Quality
  Analogies and Metaphors: Identify analogies used. Rate each as:
    Effective: Clarifies the concept for the target audience
    Partially Effective: Helpful but may confuse some learners
    Ineffective: May introduce misconceptions
  Examples: Note real-world examples. Are they relevant to adult professional \
contexts? Assess concreteness and professional relevance.
  Scaffolding: Does {instructor_name} build from foundational to advanced? Or \
jump between complexity levels? Evaluate prior-knowledge activation and clear \
"So what? / Now what?" framing.
  Adult Learning Connections: Identify moments that connect to adult learning \
principles (self-directed learning, experience-based, relevance, problem-centered, \
intrinsic motivation).

Dimension 4: Time Management and Structure
  Tangent Detection: Identify significant tangents using the operational \
definition. Record start/end timestamps for each. Compute: (Total tangent \
minutes divided by total minutes) times 100 = percent tangent time. \
Target: less than 10%.
  Pacing Balance: Flag segments that feel rushed (too much content, too fast) \
or overexplained (excessive time on simple concepts). Assess whether content \
selection favors essential over peripheral topics.
  Session Structure: Evaluate presence and quality of:
    Opening: agenda, objectives, relevance, connection to prior learning
    Signposting: transitions between topics ("Now let us move to...")
    Closing: summary, key takeaways, preview of next session
  Connect time and structure patterns to adult learners' limited time and need \
for efficient, well-organized sessions.

Step 3: Confidence Labeling and Transparency
For every quantitative metric, explicitly show the calculation and label confidence:
  HIGH: Directly countable from transcript (word count, question count)
  MODERATE: Requires interpretation but evidence is clear (analogy quality, \
understanding checks where intent must be inferred)
  LOW: Requires inference or context not in transcript (vocal tone, energy)

When confidence is MODERATE or LOW:
  Provide a point estimate plus range (e.g., "3-4 checks, plus or minus 1").
  State the reason for uncertainty.
  Provide alternative counts under stricter or looser definitions where applicable.


OUTPUT FORMAT

CRITICAL: Return ONLY a valid JSON object. No markdown, no explanation, no text \
before or after the JSON. The output will be parsed directly by json.loads().

Do NOT use any markdown syntax inside string values. No asterisks, no pound signs, \
no backticks, no pipe characters, no bullet characters. Write all string values as \
plain prose. Use plain text only.

Every key listed below MUST be present. Do not omit any key or section.

{{
  "instructor_name": "{instructor_name}",
  "session_date": "<date of session if mentioned, otherwise Not specified>",
  "session_topic": "<topic or course name>",

  "executive_summary": "<Write 3-4 sentences summarizing overall teaching \
effectiveness. Lead with the strongest positive observation. Mention 1-2 key \
growth areas. End with an encouraging forward-looking statement. Plain prose only.>",

  "metrics": {{
    "wpm": <number or null>,
    "wpm_calculation": "<e.g. 12345 words / 85 minutes = 145 WPM>",
    "wpm_confidence": "<HIGH or MODERATE or LOW>",
    "pauses_per_10min": <number or null>,
    "pauses_per_10min_calculation": "<e.g. 4 pauses / 14 minutes x 10 = 2.8 per 10 min>",
    "pauses_per_10min_confidence": "<HIGH or MODERATE or LOW>",
    "filler_words_per_min": <number or null>,
    "filler_words_per_min_calculation": "<formula with numbers>",
    "filler_words_per_min_confidence": "<HIGH or MODERATE or LOW>",
    "questions_per_5min": <number or null>,
    "questions_per_5min_calculation": "<formula with numbers>",
    "questions_per_5min_confidence": "<HIGH or MODERATE or LOW>",
    "understanding_checks_per_hour": <number or null>,
    "understanding_checks_per_hour_calculation": "<formula with numbers, including \
checks with response vs without response breakdown>",
    "understanding_checks_per_hour_confidence": "<HIGH or MODERATE or LOW>",
    "tangent_percentage": <number or null>,
    "tangent_percentage_calculation": "<formula with numbers>",
    "tangent_percentage_confidence": "<HIGH or MODERATE or LOW>",
    "curse_of_knowledge_count": <number or null>,
    "curse_of_knowledge_confidence": "<HIGH or MODERATE or LOW>"
  }},

  "strengths": [
    {{
      "number": 1,
      "title": "<short descriptive title, plain text>",
      "segment": "<A or B or C or All Segments>",
      "timestamp": "<MM:SS or HH:MM:SS from the transcript>",
      "evidence_quote": "<1-2 sentence verbatim quote from the transcript>",
      "why_effective": "<Full paragraph: why this is effective for adult learners. \
Connect to specific adult learning principles such as relevance, self-direction, \
experience-based learning, or problem-centered orientation. Plain prose only.>",
      "how_to_amplify": "<Full paragraph: a concrete, immediately implementable \
suggestion for building on this strength further. Include specific phrasing or \
techniques the instructor can try. Plain prose only.>"
    }}
  ],

  "growth_opportunities": [
    {{
      "number": 1,
      "title": "<short descriptive title, plain text>",
      "segment": "<A or B or C or All Segments>",
      "timestamp": "<MM:SS or HH:MM:SS from the transcript>",
      "evidence_quote": "<1-2 sentence verbatim quote from the transcript>",
      "why_it_matters": "<Full paragraph: why this matters for adult learners. \
Connect to adult learning principles and SME-to-teacher transition challenges. \
Plain prose only.>",
      "specific_action": "<Full paragraph: a specific, concrete action to try in \
the next session. Start with a technique name, then explain step by step how to \
implement it. Include alternative phrasing or approaches. The suggestion must be \
immediately actionable with less than 5 minutes of preparation. Plain prose only.>"
    }}
  ],

  "top_5_improvements": [
    {{
      "rank": 1,
      "title": "<short descriptive title>",
      "observation": "<1-2 sentences describing what was observed>",
      "evidence": [
        "<MM:SS Segment X - brief description of what happened>",
        "<MM:SS Segment Y - brief description of what happened>",
        "<MM:SS Segment Z - brief description of what happened>"
      ],
      "impact": "<1-2 sentences on how this affects adult learner outcomes>",
      "suggestions": "<2-3 concrete suggestions with specific techniques or \
phrasing the instructor can use>",
      "first_step": "<One small action the instructor can implement immediately \
with less than 5 minutes of preparation>"
    }}
  ],

  "timestamped_moments": [
    {{
      "timestamp": "<MM:SS or HH:MM:SS from the transcript>",
      "segment": "<A or B or C>",
      "type": "<Exemplary or Growth>",
      "context": "<Brief context: what was happening at this moment>",
      "quote": "<1-2 sentence verbatim quote from the transcript>",
      "coaching_note": "<What to notice at this moment and why it matters>",
      "suggested_reframe": "<For Growth type: an alternative approach or \
phrasing. For Exemplary type: why this moment is worth celebrating.>"
    }}
  ],

  "coaching_reflections": [
    "<A reflective question about their strongest moment in this specific session, \
grounded in a specific observation from the transcript>",
    "<A reflective question about a specific growth opportunity identified in \
this session, connecting to their development as a teacher>",
    "<A reflective question about a concrete goal for their next session, \
referencing patterns observed in this analysis>"
  ],

  "next_steps": {{
    "keep_doing": "<Identify one specific strength to maintain. Explain why it \
works for adult learners and how to sustain it. Plain prose only.>",
    "start_doing": "<Identify one specific new technique to try. Provide \
step-by-step implementation guidance that requires less than 5 minutes of \
preparation. Plain prose only.>",
    "adjust": "<Identify one specific modification to current practice. Explain \
the change and the expected impact on learner outcomes. Plain prose only.>"
  }}
}}

CONTENT RULES:
- strengths: Include 4-6 items. Sample at least one from each segment (A, B, C). \
Number them starting at 1. Every item must have the same level of detail. Do not \
abbreviate or shorten entries after the first one.
- growth_opportunities: Include 2-4 items. Sample at least one from each segment. \
Number them starting at 1. Every item must have the same level of detail.
- Maintain at least a 2:1 ratio of strengths to growth_opportunities.
- top_5_improvements: Exactly 5 items, ranked by impact on learner outcomes \
(rank 1 = highest impact). These must NOT be copies of growth_opportunities. \
They are the 5 most impactful changes ranked by priority. Each must include 3+ \
timestamped evidence examples drawn from multiple segments.
- timestamped_moments: Include 5-8 items. Mix of Exemplary and Growth types. \
Draw from all three segments. Each must include a verbatim quote.
- coaching_reflections: Exactly 3 items. Each must be a complete, thoughtful \
question that prompts genuine self-reflection. Do not use generic questions. \
Ground each question in specific observations from this session.
- next_steps: All three keys (keep_doing, start_doing, adjust) are required.
- All timestamps must be real timestamps from the transcript.
- Base all analysis on the transcript. Do not invent unsupported observations.
- Compute all metrics from the transcript text. Use null if a metric cannot \
be calculated.
- If a commonly expected behavior is not observed, state so explicitly in the \
relevant section rather than inventing observations.


TRANSCRIPT TO ANALYZE

{transcript}"""


# =============================================================================
# Comparison Prompts — Multi-video cross-session analysis
# =============================================================================

COMPARISON_SYSTEM_PROMPT = """You are a senior instructional coaching consultant \
specializing in adult learning program evaluation. You have 20+ years of experience \
analyzing teaching effectiveness across multiple sessions and instructors.

Your analytical approach:
- Pattern-focused: You identify trends, consistencies, and variations across sessions
- Evidence-based: Every observation references specific sessions and data points
- Constructive: You frame findings as opportunities, not criticisms
- Systemic: You distinguish individual instructor patterns from organizational/program issues
- Adult learning aware: You connect findings to andragogy and professional development best practices

You NEVER use evaluative language like "poor," "bad," or "failing." Instead, you \
identify patterns and frame variations as opportunities for growth or standardization.

When data shows improvement, celebrate it specifically. When data shows decline, \
frame it as an opportunity with concrete actions.

You NEVER use any markup language in your responses. No markdown, no HTML, no \
asterisks for bold, no pound signs for headings, no pipe characters for tables, \
no backticks, no bullet point characters. Use plain text only with line breaks \
and indentation for structure."""


def build_personal_performance_prompt(evaluations_data: list[dict]) -> str:
    """Build a prompt for comparing one instructor's sessions over time.

    This comparison type answers: "How has this instructor evolved?"

    Args:
        evaluations_data: List of dicts, each with:
            - label: str (e.g., "Session 1")
            - date: str (session date)
            - instructor_name: str
            - report_markdown: str (individual coaching report)
            - metrics: dict (extracted metrics from individual eval)

    Returns:
        The complete prompt string for Claude.
    """
    instructor_name = evaluations_data[0].get("instructor_name", "the instructor")
    session_count = len(evaluations_data)

    session_blocks = []
    for i, ev in enumerate(evaluations_data):
        block = _format_session_block(ev, i, include_instructor=False)
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {session_count} coaching evaluation reports for \
{instructor_name}, ordered chronologically. Generate a comprehensive performance \
comparison report that tracks growth, identifies patterns, and provides actionable \
next steps.

ANALYSIS FRAMEWORK

Step 1: Trend Analysis
For each metric tracked across sessions, determine:
  Direction: Improving, declining, stable, or inconsistent
  Rate of change: Rapid improvement, gradual improvement, plateau, etc.
  Outliers: Sessions that deviate significantly from the trend

Step 2: Pattern Recognition
Identify:
  Consistent strengths: What {instructor_name} does well across ALL sessions
  Consistent growth areas: What needs attention in MOST sessions
  Emerging skills: New strengths that appear in later sessions
  Regression areas: Skills that were strong but have declined

Step 3: Impact Assessment
For each finding, assess:
  How it affects adult learner engagement and outcomes
  Whether the pattern suggests a habit (consistent) or situational factor

OUTPUT FORMAT

Use plain text only. No markdown, no asterisks, no pound signs, no pipe \
characters, no backticks. Use the exact section headers shown below (in all \
caps) on their own line. Every section is REQUIRED.


EXECUTIVE SUMMARY

Write 4-5 sentences summarizing the overall trajectory. Lead with the most \
significant improvement. Mention the most important area still needing growth. \
End with an encouraging forward-looking statement about {instructor_name}'s development.


METRIC TRENDS

For each of the core metrics (WPM, Pauses per 10 min, Filler Words per min, \
Questions per 5 min, Understanding Checks per hour, Tangent Percentage), present:
  The starting value, ending value, and direction of trend
  Whether {instructor_name} is meeting the target consistently
  Any notable shifts or outliers

Present as a structured summary, one metric per block.


CROSS-SESSION STRENGTHS

List 3-5 strengths that appear across multiple sessions. For each:
  Strength title
  Sessions where this was observed
  How this strength has evolved over time
  Recommendation to amplify it further


CROSS-SESSION GROWTH OPPORTUNITIES

List 2-4 growth areas that persist across sessions. For each:
  Growth area title
  Sessions where this was observed
  Whether there has been any progress on this area
  Specific, progressive action plan (what to try in the next 2-3 sessions)


IMPROVEMENT HIGHLIGHTS

List 2-3 areas where {instructor_name} has shown the most improvement. For each:
  Improvement title
  Where it started (earliest session evidence)
  Where it is now (latest session evidence)
  What likely contributed to the improvement


PRIORITIZED ACTION PLAN

Rank the top 5 actions for {instructor_name}'s continued development. For each:
  Action title
  Current state across sessions
  Specific target to aim for
  Suggested timeline (next session, next 3 sessions, ongoing)
  Expected impact on adult learners


COACHING REFLECTIONS

Write 3-4 reflective questions for {instructor_name} about their growth trajectory. \
Ground each question in specific patterns observed across the sessions analyzed.


NEXT STEPS

List 3 concrete goals for the next evaluation period:
  1. One strength to maintain and deepen
  2. One skill that is improving with a specific target to hit
  3. One persistent growth area with a new strategy to try


---
Analysis generated by Adult Learning Coaching Agent
Analysis type: Personal Performance Tracking


EVALUATION REPORTS TO COMPARE

{sessions_text}"""


def build_class_delivery_prompt(
    evaluations_data: list[dict],
    class_tag: str = "the class",
) -> str:
    """Build a prompt for comparing different instructors teaching the same class.

    This comparison type answers: "How do different instructors deliver the same material?"

    Args:
        evaluations_data: List of dicts (same structure as personal_performance).
        class_tag: Name/identifier of the class being compared.

    Returns:
        The complete prompt string for Claude.
    """
    instructor_count = len(evaluations_data)

    session_blocks = []
    for i, ev in enumerate(evaluations_data):
        block = _format_session_block(ev, i, include_instructor=True)
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {instructor_count} coaching evaluation reports \
for different instructors delivering "{class_tag}". Generate a comparative analysis \
that identifies delivery patterns, best practices, and opportunities for \
standardization.

ANALYSIS FRAMEWORK

Step 1: Delivery Variation Analysis
For each metric and dimension, compare across instructors:
  Range: What is the spread between highest and lowest?
  Consistency: Do most instructors cluster around similar values?
  Outliers: Any instructor significantly above or below the group?

Step 2: Best Practices Extraction
Identify:
  Universal strengths: Techniques ALL instructors use effectively
  Unique strengths: Excellent techniques used by only 1-2 instructors \
that others could adopt
  Common gaps: Growth areas that appear across multiple instructors \
(may indicate a curriculum design issue, not an instructor issue)
  Delivery divergence: Places where instructors take significantly \
different approaches to the same material

Step 3: Curriculum vs. Instructor Analysis
Distinguish between:
  Issues caused by the curriculum/materials (all instructors struggle in \
the same places, suggesting materials redesign)
  Issues caused by individual instructor skills (only some instructors \
struggle, suggesting targeted coaching)

OUTPUT FORMAT

Use plain text only. No markdown, no asterisks, no pound signs, no pipe \
characters, no backticks. Use the exact section headers shown below (in all \
caps) on their own line. Every section is REQUIRED.


EXECUTIVE SUMMARY

Write 4-5 sentences summarizing the delivery landscape. Note the overall quality \
level, key variations, and the most actionable finding. Identify whether most \
variation is instructor-driven or curriculum-driven.


INSTRUCTOR COMPARISON

For each core metric (WPM, Pauses per 10 min, Filler Words per min, Questions \
per 5 min, Understanding Checks per hour, Tangent Percentage), present each \
instructor's value, the group average, and whether individual values are on target.

Present as a structured summary, one metric per block, with each instructor listed.


BEST PRACTICES TO SHARE

List 3-5 techniques from top-performing deliveries that ALL instructors should adopt. \
For each:
  Practice title
  Which instructor(s) demonstrated this
  Specific example from their report
  How other instructors can incorporate it
  Expected impact on learner experience


COMMON DELIVERY GAPS

List 2-4 areas where multiple instructors struggle. For each:
  Gap title
  How many instructors show this pattern
  Whether this is likely an instructor issue or curriculum issue
  Recommended action (coaching for instructors vs. redesigning materials)


CURRICULUM INSIGHTS

Based on cross-instructor patterns:
  Areas where the curriculum supports effective delivery
  Areas where the curriculum may need revision (all instructors struggle)
  Suggested content or structure changes


INDIVIDUAL INSTRUCTOR NOTES

For each instructor, provide 2-3 sentences of personalized feedback:
  What they do uniquely well (that others could learn from)
  Their most impactful growth opportunity


PRIORITIZED RECOMMENDATIONS

Rank the top 5 actions for the training program. For each:
  Recommendation title
  Scope: All instructors, specific instructors, or curriculum change
  Expected impact on learner outcomes
  Implementation difficulty (Easy, Medium, or Hard)


NEXT STEPS

  1. One program-wide change to implement
  2. One best practice to formalize in instructor training
  3. One curriculum modification to consider


---
Analysis generated by Adult Learning Coaching Agent
Analysis type: Class Delivery Comparison


EVALUATION REPORTS TO COMPARE

{sessions_text}"""


def build_program_evaluation_prompt(evaluations_data: list[dict]) -> str:
    """Build a prompt for evaluating overall program delivery quality.

    This comparison type answers: "Is this program consistent and effective?"

    Args:
        evaluations_data: List of dicts (same structure as personal_performance).

    Returns:
        The complete prompt string for Claude.
    """
    session_count = len(evaluations_data)

    session_blocks = []
    for i, ev in enumerate(evaluations_data):
        block = _format_session_block(ev, i, include_instructor=True)
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {session_count} coaching evaluation reports \
from a training program. Generate a comprehensive program evaluation that assesses \
delivery consistency, content quality, and curricular design.

ANALYSIS FRAMEWORK

Step 1: Delivery Consistency Analysis
Across all sessions:
  Metric consistency: How much do core metrics vary? High variance = \
inconsistent learner experience
  Quality floor: What is the minimum quality level? (Most impactful for learners)
  Quality ceiling: What is the best performance? (Shows what is possible)

Step 2: Content Consistency
  Are the same topics covered at similar depth?
  Are there significant content gaps in some sessions?
  Is the level of rigor consistent?

Step 3: Curricular Design Assessment
  Does the program have a coherent learning progression?
  Are there systemic issues that appear across multiple sessions?
  What patterns suggest structural problems vs. individual performance?

Step 4: Impact on Adult Learners
  How does the variation affect the learner experience?
  Are adult learning principles consistently applied?
  What is the likely impact on learning outcomes?

OUTPUT FORMAT

Use plain text only. No markdown, no asterisks, no pound signs, no pipe \
characters, no backticks. Use the exact section headers shown below (in all \
caps) on their own line. Every section is REQUIRED.


EXECUTIVE SUMMARY

Write 5-6 sentences providing a program-level assessment. Cover:
  1. Overall program quality (high-level impression)
  2. Delivery consistency (high, moderate, or low)
  3. Most significant finding
  4. Impact on adult learners
  5. Key recommendation


PROGRAM METRICS OVERVIEW

Aggregate metrics across all sessions. For each core metric (WPM, Pauses per \
10 min, Filler Words per min, Questions per 5 min, Understanding Checks per hour, \
Tangent Percentage), present:
  Minimum value, Maximum value, Average, and range of variation
  Target value
  Consistency rating: HIGH (low variance), MODERATE, or LOW (high variance)


DELIVERY CONSISTENCY ASSESSMENT

Evaluate these aspects:
  Opening quality: Do sessions consistently set objectives and connect to prior learning?
  Engagement levels: Is learner interaction consistent across sessions?
  Explanation approaches: Are teaching methods similar in quality?
  Closing quality: Do sessions consistently summarize and preview?
  Overall consistency rating: HIGH, MODERATE, or LOW


CONTENT CONSISTENCY ASSESSMENT

  Topic coverage: Are all required topics addressed consistently?
  Depth consistency: Is the level of detail similar across sessions?
  Example quality: Are real-world examples consistently relevant to adult professionals?


CURRICULAR DESIGN FINDINGS

Identify systemic patterns:
  Design strengths: What the curriculum does well (appears in most sessions)
  Design gaps: What is missing or problematic (appears across sessions)
  Structural issues: Pacing problems, content sequencing, prerequisite gaps


PROGRAM STRENGTHS

List 3-5 program-wide strengths. For each:
  Strength title
  How many sessions demonstrate this
  Impact on adult learner experience
  How to institutionalize this strength


AREAS FOR IMPROVEMENT

List 3-5 program-wide improvement areas. For each:
  Improvement area title
  Scope: Instructor training, curriculum redesign, or program structure
  How many sessions show this issue
  Recommended action with expected impact


IMPACT ANALYSIS

Assess the likely impact on adult learners:
  Engagement: How does delivery variation affect learner engagement?
  Learning outcomes: What patterns support or hinder learning?
  Professional relevance: Is content consistently relevant to learners' work?
  Consistency of experience: Will learners get a comparable experience \
regardless of session or instructor?


PRIORITIZED ACTION ITEMS

Rank the top 5 program-level actions. For each:
  Action title
  Category: Instructor development, Curriculum, Program design, or Quality assurance
  Expected impact on learner outcomes
  Implementation difficulty (Easy, Medium, or Hard)
  Suggested timeline


NEXT STEPS

  1. Immediate: One change to implement before the next session cycle
  2. Short-term: One project for the next quarter
  3. Long-term: One strategic initiative for the program


---
Analysis generated by Adult Learning Coaching Agent
Analysis type: Program Evaluation


EVALUATION REPORTS TO COMPARE

{sessions_text}"""


# =============================================================================
# Helpers
# =============================================================================


def _format_session_block(ev: dict, index: int, include_instructor: bool = True) -> str:
    """Format a single evaluation dict into a text block for comparison prompts.

    Centralizes the session-block formatting that was previously duplicated
    across the three comparison prompt builders.
    """
    name = ev.get("instructor_name", f"Instructor {index + 1}")
    label = ev.get("label", f"Session {index + 1}")
    date = ev.get("date", "Not specified")
    metrics_text = _format_metrics(ev.get("metrics", {}))
    report = ev.get("report_markdown", "No report available.")

    header = f"SESSION: {label}"
    instructor_line = f"Instructor: {name}\n" if include_instructor else ""

    return f"""{header}
{instructor_line}Date: {date}
Key Metrics: {metrics_text}

Individual Coaching Report:
{report}
"""


def _format_metrics(metrics: dict) -> str:
    """Format a metrics dict as a readable one-line summary.

    Used inside comparison prompts to give Claude a quick numeric overview
    of each session before the full report.
    """
    if not metrics:
        return "No metrics available"

    parts = []
    label_map = {
        "wpm": "WPM",
        "pauses_per_10min": "Pauses/10min",
        "filler_words_per_min": "Fillers/min",
        "questions_per_5min": "Questions/5min",
        "understanding_checks_per_hour": "Checks/hr",
        "tangent_percentage": "Tangent%",
        "curse_of_knowledge_count": "CoK instances",
    }
    for key, label in label_map.items():
        if key in metrics:
            value = metrics[key]
            parts.append(f"{label}: {value}")

    return " | ".join(parts) if parts else "No standard metrics"


# Map comparison type strings to their prompt builders
COMPARISON_PROMPT_BUILDERS = {
    "personal_performance": build_personal_performance_prompt,
    "class_delivery": build_class_delivery_prompt,
    "program_evaluation": build_program_evaluation_prompt,
}
