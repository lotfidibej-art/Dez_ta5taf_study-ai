# Adaptive AI Learning Companion

An AI-powered study platform designed to replace passive reading and surface memorization with **deep, durable understanding**.

Instead of giving generic, one-size-fits-all answers, the platform diagnoses how well a student actually understands a concept—using both text and voice signals—and dynamically adapts its teaching strategy, interface, and difficulty level in real time.

---

## What Problem Does It Solve?

Most students study passively: re-reading notes, highlighting textbooks, or memorizing definitions without truly grasping *why* a concept works. Standard AI chatbots make this worse by immediately handing over complete answers.

This platform flips the learning process:
- **Never gives away the full answer prematurely.**
- **Detects hesitation and rote memorization** through voice cadence and response patterns.
- **Adapts to how you learn best in each subject** (e.g., visual diagrams for Literature vs. faded coding problems for Computer Science).

---

## Key Features

### 1. Dual Learning Modes
- **AI-Guided Mode:** Upload any study resource (PDFs, lecture videos, slides, or links), take a quick 3-question diagnostic, and let the AI orchestrate a personalized step-by-step mastery path.
- **Self-Guided Mode:** Explore your documents, summaries, and interactive sandboxes at your own pace, summoning AI explanations, hints, or quizzes whenever you get stuck.

### 2. Three Adaptive Mastery Tiers
As your live **Comprehension Rating (`0% – 100%`)** evolves during a session, the workspace automatically transforms:
- **Foundation (`< 40%`):** Breaks topics into crisp bullet points, generates visual diagrams (Mermaid.js), builds analogies from concepts you already mastered in past sessions, and embeds live **Interactive Labs** (PhET, Desmos, CodeSandbox).
- **Guided Practice (`40% – 75%`):** Uses **Faded Worked Examples** (showing the first steps and letting you complete the rest) paired with a 3-level **Contingent Hint Ladder** that nudges you without spoiling the solution.
- **Deep Mastery (`> 75%`):** Challenges you with **Hidden Misconception Traps** (*"Spot the subtle flaw in this explanation"*) and **Protégé Mode** (*"Teach the concept to the AI while it asks tough follow-up questions"*).

### 3. Voice Recognition & Fluency Intelligence
Students can answer questions and teach concepts out loud. Beyond transcribing words, the system analyzes **speech pace, pauses, and filler words** to distinguish confident, causal understanding from memorized recitation—offering gentle study-habit coaching when needed.

### 4. Cross-Session & Subject-Specific Memory
- **Domain-Aware Adaptation:** Tracks which teaching methods work best for you in each specific academic field and prioritizes them automatically.
- **Cross-Domain Analogies:** Remembers concepts you mastered weeks ago across *any* subject and uses them as mental bridges to explain brand-new topics.

### 5. Post-Session Résumés, Mini-Exams & Analytics
- **Adaptive Mini-Exams:** Generates targeted end-of-session tests built around the exact misconceptions you struggled with earlier.
- **Refresher Résumé Cards:** Automatically summarizes every completed session into a scannable cheat sheet (*Core Mental Model*, *Winning Analogies*, and *Misconceptions Conquered*) for future review.
- **Learning Analytics Dashboard:** Visualizes your **Mastery per Field**, **Best Learning Styles**, **Mastery Speed Over Time**, and **Lessons Learned**.

---

## High-Level Architecture

The end-to-end execution flow across the Frontend UI, LangGraph Orchestrator, specialized sub-agents, and dual memory layer (`Redis` + `PostgreSQL/pgvector`) is illustrated below:

![Adaptive AI Learning System Sequence Diagram](docs/architecture-sequence.png)

> *Diagram source available at [`docs/architecture-sequence.puml`](docs/architecture-sequence.puml).*

---

## Roadmap

- [x] Multimodal resource ingestion & semantic concept chunking
- [x] Comprehension-driven state machine (Foundation $\rightarrow$ Scaffolding $\rightarrow$ Mastery)
- [x] Voice prosody & hesitation analysis for Protégé Mode
- [x] Domain-specific learning style weighting & cross-session analogies
- [ ] Spaced-repetition scheduling for Session Résumé refreshers
- [ ] Collaborative study rooms & peer misconception challenges
