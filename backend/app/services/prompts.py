"""
Coaching analysis prompt templates.

This is the most important file in the entire application.
The prompt defines HOW Claude analyzes teaching — it IS the product logic.

The PRD references "Coaching-Prompt_v4.md" (~13,000 chars). This module
implements that framework with structured sections that map to the PRD's
4 analysis dimensions.

Key design decisions:
1. System prompt sets the role and constraints
2. Analysis instructions define the 4 dimensions + metrics
3. Output format is structured markdown (easy to parse into PDF later)
4. Sampling strategy ensures balanced evidence across the full session
5. 2:1 strength-to-improvement ratio keeps feedback motivational

Comparison prompts (added for multi-video analysis):
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
and instructors deserve to hear what's working.

You NEVER use any markup language in your responses. No markdown, no HTML, no \
asterisks for bold, no pound signs for headings, no pipe characters for tables, \
no backticks, no bullet point characters. Use plain text only."""


def build_analysis_prompt(transcript: str, instructor_name: str = "the instructor") -> str:
    """Build the full analysis prompt for Claude.

    This is the core "algorithm" of the product. It instructs Claude to:
    1. Divide the transcript into 3 segments
    2. Analyze 4 dimensions with specific metrics
    3. Extract evidence with timestamps
    4. Calculate metrics with shown formulas
    5. Generate a structured coaching report

    The output uses plain text with clearly labeled section headers
    (no markdown, no HTML, no markup of any kind). Each section uses
    a consistent "SECTION_NAME:" header followed by structured sub-elements
    with labeled fields. This format is easy to parse programmatically
    and renders cleanly in PDF reports.

    Args:
        transcript: The full timestamped transcript text.
        instructor_name: Name of the instructor (for personalization).

    Returns:
        The complete prompt string to send to Claude.
    """
    return f"""Analyze the following transcript of a distance learning session \
taught by {instructor_name}. Generate a comprehensive coaching report following \
the structure and requirements below exactly.


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

CRITICAL: Do not use any markup language in your response. No markdown, no HTML, \
no asterisks for bold, no pound signs for headings, no pipe characters for tables, \
no backticks, no bullet point characters. Use plain text only. Use line breaks and \
indentation for structure. Use the exact section headers shown below (in all caps) \
on their own line. Every section listed below is REQUIRED and must appear in your \
response with complete content.

Your response must contain ALL of the following sections in this exact order. \
Do not skip any section. Do not combine sections. Each section header must appear \
on its own line exactly as shown.


EXECUTIVE SUMMARY

Write 3-4 sentences summarizing overall teaching effectiveness. Lead with the \
strongest positive observation. Mention 1-2 key growth areas. End with an \
encouraging forward-looking statement. Frame as developmental and growth-oriented. \
Write this as a plain paragraph.


STRENGTHS TO BUILD ON

List 3-5 strengths with evidence. You MUST include the full detail for EVERY \
strength, not just the first one. Sample at least one strength from each segment \
(A, B, C). For each strength, use this exact format:

[number]. [Strength title]
Why this is effective:
[Write a full paragraph explaining why this is effective. Connect to specific \
adult learning principles. Include a timestamp citation in MM:SS or HH:MM:SS \
format showing where this was observed, labeled with its segment letter. Include \
a brief direct quote from the transcript as evidence.]
How to amplify:
[Write a full paragraph with a concrete, immediately implementable suggestion \
for how to build on this strength further.]

Repeat this complete format for every single strength. Do not abbreviate or \
shorten entries after the first one. Every strength must have the same level \
of detail as the first.


GROWTH OPPORTUNITIES

List 2-3 growth areas with evidence. You MUST include the full detail for EVERY \
growth opportunity, not just the first one. Sample at least one growth area from \
each segment. For each growth area, use this exact format:

[number]. [Growth area title]
Why this matters:
[Write a full paragraph explaining why this matters for adult learners. Connect \
to adult learning principles and SME-to-teacher challenges. Include a timestamp \
citation in MM:SS or HH:MM:SS format showing where this was observed, labeled \
with its segment letter. Include a brief direct quote from the transcript as \
evidence.]
Specific action to try:
[Write a full paragraph describing a specific, concrete action to try in the \
next session. Start with a technique name, then explain step by step how to \
implement it. Include alternative phrasing or approaches where useful. The \
suggestion must be immediately actionable with less than 5 minutes of preparation.]

Repeat this complete format for every single growth opportunity. Do not abbreviate \
or shorten entries after the first one. Every growth opportunity must have the same \
level of detail as the first.


TOP 5 PRIORITIZED IMPROVEMENTS

Rank the 5 most impactful changes {instructor_name} could make, from highest \
to lowest impact. This section is REQUIRED and must contain exactly 5 items. \
For each improvement, use this exact format:

[number]
[One-sentence description of the recommended improvement]
[One-sentence explanation of why this is ranked at this priority level, focusing \
on the expected impact on learner outcomes.]

Repeat this complete format for all 5 improvements. Do not skip any.


TIMESTAMPED MOMENTS TO REVIEW

List 5-8 specific moments from the session that {instructor_name} should re-watch. \
This section is REQUIRED and must contain at least 5 entries. Mix both exemplary \
moments and moments to improve. Draw from all three segments. For each moment, \
use this exact format:

[MM:SS] [Exemplary or Improve] [Brief context] [Description of what to notice \
at this moment and why it matters. For Improve moments, include a suggested \
reframe or alternative approach.]

Repeat this format for every moment. Include at least 5 entries.


METRICS SNAPSHOT

Present all calculated metrics in this exact format, one per line. This section \
is REQUIRED.

Speaking Pace: [value] WPM (Target: 120-160) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Strategic Pauses: [value] per 10 min (Target: 4-6) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Filler Words: [value] per min (Target: fewer than 3) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Questions Asked: [value] per 5 min (Target: more than 1) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Understanding Checks: [value] per hour (Target: 6-8) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Tangent Time: [value]% (Target: less than 10%) [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]
Curse of Knowledge Instances: [value] total [On Target or Near Target or Needs Focus] Confidence: [HIGH or MODERATE or LOW]

After listing all metrics, show the full calculation for each metric with the \
formula, the numbers, and the result. For metrics with MODERATE or LOW confidence, \
include the uncertainty range and reason.


COACHING REFLECTIONS

Write exactly 3 reflective questions for {instructor_name}. This section is \
REQUIRED. Use this exact format:

1. [A reflective question about their strongest moment in this session]
2. [A reflective question about a specific growth opportunity]
3. [A reflective question about their goals for the next session]

Each question must be a complete, thoughtful question that prompts genuine \
self-reflection. Do not use generic questions. Ground each question in specific \
observations from this session.


NEXT STEPS

List exactly 3 concrete actions for {instructor_name}'s next session. This \
section is REQUIRED. Use this exact format:

1. Keep doing: [specific strength to maintain, with brief explanation of why \
it works and how to sustain it]
2. Start doing: [specific new technique to try, with step-by-step implementation \
guidance that requires less than 5 minutes of preparation]
3. Adjust: [specific modification to current practice, with brief explanation \
of the change and expected impact]


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
frame it as an opportunity with concrete actions."""


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

    # Build the session summaries
    session_blocks = []
    for i, ev in enumerate(evaluations_data):
        block = f"""### {ev.get('label', f'Session {i + 1}')}
**Date:** {ev.get('date', 'Not specified')}
**Key Metrics:** {_format_metrics(ev.get('metrics', {}))}

**Individual Coaching Report:**
{ev.get('report_markdown', 'No report available.')}
"""
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {session_count} coaching evaluation reports for \
{instructor_name}, ordered chronologically. Generate a comprehensive performance \
comparison report that tracks growth, identifies patterns, and provides actionable \
next steps.

## ANALYSIS FRAMEWORK

### Step 1: Trend Analysis
For each metric tracked across sessions, determine:
- **Direction:** Improving, declining, stable, or inconsistent
- **Rate of change:** Rapid improvement, gradual improvement, plateau, etc.
- **Outliers:** Sessions that deviate significantly from the trend

### Step 2: Pattern Recognition
Identify:
- **Consistent strengths:** What {instructor_name} does well across ALL sessions
- **Consistent growth areas:** What needs attention in MOST sessions
- **Emerging skills:** New strengths that appear in later sessions
- **Regression areas:** Skills that were strong but have declined

### Step 3: Impact Assessment
For each finding, assess:
- How it affects adult learner engagement and outcomes
- Whether the pattern suggests a habit (consistent) or situational factor

## OUTPUT FORMAT

# Performance Comparison: {instructor_name}
## {session_count} Sessions Analyzed

## Executive Summary
Write 4-5 sentences summarizing the overall trajectory. Lead with the most \
significant improvement. Mention the most important area still needing growth. \
End with an encouraging forward-looking statement about the instructor's development.

## Metric Trends
For each of the 5 core metrics (WPM, Pauses, Filler Words, Questions, Tangent %), \
present:
- A summary of the trend across sessions
- The starting value, ending value, and direction
- Whether the instructor is meeting the target consistently

| Metric | Earliest | Latest | Trend | Target | Status |
|--------|----------|--------|-------|--------|--------|
| (fill for each metric) |

## Cross-Session Strengths
List 3-5 strengths that appear across multiple sessions:
- **Strength title**
  - Sessions where this was observed
  - How this strength has evolved
  - Recommendation to amplify further

## Cross-Session Growth Opportunities
List 2-4 growth areas that persist across sessions:
- **Growth area title**
  - Sessions where this was observed
  - Whether there's been any progress on this area
  - Specific, progressive action plan (what to try in the next 2-3 sessions)

## Improvement Highlights
List 2-3 areas where {instructor_name} has shown the most improvement:
- **Improvement title**
  - Where it started (earliest session evidence)
  - Where it is now (latest session evidence)
  - What likely contributed to the improvement

## Prioritized Action Plan
Rank the top 5 actions for {instructor_name}'s continued development:
1. **Action title**
   - Current state across sessions
   - Specific target to aim for
   - Suggested timeline (next session, next 3 sessions, ongoing)
   - Expected impact on adult learners

## Coaching Reflections
Write 3-4 reflective questions for {instructor_name} about their growth trajectory.

## Next Steps
List 3 concrete goals for the next evaluation period:
1. One strength to maintain and deepen
2. One skill that's improving — specific target to hit
3. One persistent growth area — new strategy to try

---
*Comparison generated by Adult Learning Coaching Agent*
*Analysis type: Personal Performance Tracking*

## EVALUATION REPORTS TO COMPARE

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
        name = ev.get("instructor_name", f"Instructor {i + 1}")
        block = f"""### {ev.get('label', name)}
**Instructor:** {name}
**Date:** {ev.get('date', 'Not specified')}
**Key Metrics:** {_format_metrics(ev.get('metrics', {}))}

**Individual Coaching Report:**
{ev.get('report_markdown', 'No report available.')}
"""
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {instructor_count} coaching evaluation reports \
for different instructors delivering "{class_tag}". Generate a comparative analysis \
that identifies delivery patterns, best practices, and opportunities for \
standardization.

## ANALYSIS FRAMEWORK

### Step 1: Delivery Variation Analysis
For each metric and dimension, compare across instructors:
- **Range:** What's the spread between highest and lowest?
- **Consistency:** Do most instructors cluster around similar values?
- **Outliers:** Any instructor significantly above or below the group?

### Step 2: Best Practices Extraction
Identify:
- **Universal strengths:** Techniques ALL instructors use effectively
- **Unique strengths:** Excellent techniques used by only 1-2 instructors \
that others could adopt
- **Common gaps:** Growth areas that appear across multiple instructors \
(may indicate a curriculum design issue, not an instructor issue)
- **Delivery divergence:** Places where instructors take significantly \
different approaches to the same material

### Step 3: Curriculum vs. Instructor Analysis
Distinguish between:
- Issues caused by the curriculum/materials (all instructors struggle in \
the same places → redesign the materials)
- Issues caused by individual instructor skills (only some instructors \
struggle → provide targeted coaching)

## OUTPUT FORMAT

# Class Delivery Comparison: {class_tag}
## {instructor_count} Instructors Compared

## Executive Summary
Write 4-5 sentences summarizing the delivery landscape. Note the overall quality \
level, key variations, and the most actionable finding. Identify whether most \
variation is instructor-driven or curriculum-driven.

## Instructor Comparison Matrix
Create a comparison table:

| Dimension | {' | '.join(f'Instructor {i+1}' for i in range(instructor_count))} | Avg |
|-----------|{'|'.join(['----|' for _ in range(instructor_count)])} ---|
| WPM | | | |
| Pauses per 10 min | | | |
| Filler words per min | | | |
| Questions per 5 min | | | |
| Tangent % | | | |
| Overall engagement | | | |
| Explanation quality | | | |

## Best Practices to Share
List 3-5 techniques from top-performing deliveries that ALL instructors should adopt:
- **Practice title**
  - Which instructor(s) demonstrated this
  - Specific example from their report
  - How other instructors can incorporate it
  - Expected impact on learner experience

## Common Delivery Gaps
List 2-4 areas where multiple instructors struggle:
- **Gap title**
  - How many instructors show this pattern
  - Whether this is likely an instructor issue or curriculum issue
  - Recommended action (coaching for instructors vs. redesigning materials)

## Curriculum Insights
Based on cross-instructor patterns:
- Areas where the curriculum supports effective delivery
- Areas where the curriculum may need revision (all instructors struggle)
- Suggested content or structure changes

## Individual Instructor Notes
For each instructor, provide 1-2 sentences of personalized feedback:
- What they do uniquely well (that others could learn from)
- Their most impactful growth opportunity

## Prioritized Recommendations
Rank the top 5 actions for the training program:
1. **Recommendation title**
   - Scope: All instructors / specific instructors / curriculum change
   - Expected impact
   - Implementation difficulty (Easy / Medium / Hard)

## Next Steps
1. One program-wide change to implement
2. One best practice to formalize in instructor training
3. One curriculum modification to consider

---
*Comparison generated by Adult Learning Coaching Agent*
*Analysis type: Class Delivery Comparison*

## EVALUATION REPORTS TO COMPARE

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
        name = ev.get("instructor_name", f"Instructor {i + 1}")
        block = f"""### {ev.get('label', f'Session {i + 1}')}
**Instructor:** {name}
**Date:** {ev.get('date', 'Not specified')}
**Key Metrics:** {_format_metrics(ev.get('metrics', {}))}

**Individual Coaching Report:**
{ev.get('report_markdown', 'No report available.')}
"""
        session_blocks.append(block)

    sessions_text = "\n---\n".join(session_blocks)

    return f"""Analyze the following {session_count} coaching evaluation reports \
from a training program. Generate a comprehensive program evaluation that assesses \
delivery consistency, content quality, and curricular design.

## ANALYSIS FRAMEWORK

### Step 1: Delivery Consistency Analysis
Across all sessions:
- **Metric consistency:** How much do core metrics vary? High variance = \
inconsistent learner experience
- **Quality floor:** What's the minimum quality level? (Most impactful for learners)
- **Quality ceiling:** What's the best performance? (Shows what's possible)

### Step 2: Content Consistency
- Are the same topics covered at similar depth?
- Are there significant content gaps in some sessions?
- Is the level of rigor consistent?

### Step 3: Curricular Design Assessment
- Does the program have a coherent learning progression?
- Are there systemic issues that appear across multiple sessions?
- What patterns suggest structural problems vs. individual performance?

### Step 4: Impact on Adult Learners
- How does the variation affect the learner experience?
- Are adult learning principles consistently applied?
- What is the likely impact on learning outcomes?

## OUTPUT FORMAT

# Program Evaluation Report
## {session_count} Sessions Analyzed

## Executive Summary
Write 5-6 sentences providing a program-level assessment. Cover:
1. Overall program quality (high-level impression)
2. Delivery consistency (high/moderate/low)
3. Most significant finding
4. Impact on adult learners
5. Key recommendation

## Program Metrics Overview
Aggregate metrics across all sessions:

| Metric | Min | Max | Average | Std Dev | Target | Consistency |
|--------|-----|-----|---------|---------|--------|-------------|
| (fill for each core metric) |

Rate consistency as HIGH (low variance), MODERATE, or LOW (high variance).

## Delivery Consistency Assessment
Evaluate these aspects:
- **Opening quality:** Do sessions consistently set objectives and connect to prior learning?
- **Engagement levels:** Is learner interaction consistent across sessions?
- **Explanation approaches:** Are teaching methods similar in quality?
- **Closing quality:** Do sessions consistently summarize and preview?
- **Overall rating:** HIGH / MODERATE / LOW consistency

## Content Consistency Assessment
- **Topic coverage:** Are all required topics addressed consistently?
- **Depth consistency:** Is the level of detail similar across sessions?
- **Example quality:** Are real-world examples consistently relevant?

## Curricular Design Findings
Identify systemic patterns:
- **Design strengths:** What the curriculum does well (appears in most sessions)
- **Design gaps:** What's missing or problematic (appears across sessions)
- **Structural issues:** Pacing problems, content sequencing, prerequisite gaps

## Strengths Across the Program
List 3-5 program-wide strengths:
- **Strength title**
  - How many sessions demonstrate this
  - Impact on adult learner experience
  - How to institutionalize this strength

## Areas for Improvement
List 3-5 program-wide improvement areas:
- **Improvement area**
  - Scope: Instructor training / curriculum redesign / program structure
  - How many sessions show this issue
  - Recommended action

## Impact Analysis
Assess the likely impact on adult learners:
- **Engagement:** How does delivery variation affect learner engagement?
- **Learning outcomes:** What patterns support or hinder learning?
- **Professional relevance:** Is content consistently relevant to learners' work?
- **Consistency of experience:** Will learners get a comparable experience \
regardless of session/instructor?

## Prioritized Action Items
Rank the top 5 program-level actions:
1. **Action title**
   - Category: Instructor development / Curriculum / Program design / Quality assurance
   - Expected impact on learner outcomes
   - Implementation difficulty
   - Suggested timeline

## Next Steps
1. Immediate: One change to implement before the next session cycle
2. Short-term: One project for the next quarter
3. Long-term: One strategic initiative for the program

---
*Comparison generated by Adult Learning Coaching Agent*
*Analysis type: Program Evaluation*

## EVALUATION REPORTS TO COMPARE

{sessions_text}"""


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
        "tangent_percentage": "Tangent%",
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
