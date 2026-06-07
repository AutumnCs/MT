# MeituanAgent UI Spec for Stitch

This document describes the frontend experience in product terms so Stitch can design the UI system and page layouts.

## 1. Product Goal

Turn a user’s free-form trip request into a clear, actionable route plan with:

- natural-language input
- lightweight preference selection
- one-step clarification when the request is too vague
- route comparison
- route modification
- route explanation
- knowledge explanation
- map / route diagnostics

The UI should feel like a polished consumer travel assistant, not a dashboard.

## 2. Core UX Principles

- Make it easy to start: users should know what to type within 3 seconds.
- Make it easy to confirm: when the system is unsure, ask one focused question only.
- Make it easy to compare: show multiple route options, not just one answer.
- Make it easy to modify: users should be able to say “too far / too expensive / no queue” and adjust quickly.
- Make it easy to trust: show “system understanding”, route rationale, and helpful diagnostics.
- Make it easy to recover: always have a fallback when data is missing or the answer is vague.

## 3. Visual Direction

- Overall mood: warm, clean, friendly, slightly premium.
- Brand accent: golden yellow / warm amber.
- Background: soft off-white / light gray with subtle gradients.
- Cards: rounded corners, soft shadows, lots of spacing.
- Typography: clear hierarchy, strong heading, short supportive copy.
- Icons: simple line icons, slightly playful but not childish.
- Motion: light fade / slide transitions, no heavy animation.

## 4. Main Information Architecture

### Primary pages

1. Home / input page
2. Clarification page
3. Route result page
4. Knowledge explanation page

### Supporting states

- loading
- empty input
- API error
- no route found
- clarification needed
- map unavailable
- route modified
- route comparison

## 5. Page-by-Page Spec

## 5.1 Home / Input Page

### Purpose

Let the user quickly express a trip request and trigger route generation.

### Current behaviors to preserve

- city selection
- quick examples
- preference chips
- natural language text input
- generate CTA
- auto-fill text when a chip is selected
- scroll to input / examples when needed

### Recommended layout

#### Top section

- App title / brand mark
- city switcher between:
  - Guangzhou
  - Shanghai
- short welcome subtitle

#### Hero / search area

- large search-like input card
- text field with placeholder prompting a natural-language request
- primary CTA: “Generate Route”
- optional voice/search icon hint

#### Quick preference chips

- couple / photo / no queue / value / relaxed / food / culture / night view
- chip state:
  - default
  - selected
  - selected with accent highlight
- when selected, chip text can be appended into the request text area

#### Example requests

- 3 example cards at most
- each example should be short enough to scan quickly
- clicking an example fills the text field and can also auto-switch city

#### Function guide block

- a “what this app can do” section
- should help first-time users understand capabilities
- examples:
  - input a trip request
  - compare route options
  - refine with preferences
  - ask for clarification
  - explain the route logic

### Home page states

- empty: show examples and chips
- filled: show CTA enabled
- loading: disable CTA and show status messages
- error: toast/snackbar or inline error card

### Key interactions

- select city
- toggle preference chip
- tap example request
- enter free-form text
- generate route

## 5.2 Clarification Page

### Purpose

When the request is too vague, ask exactly one focused question and continue.

### Core interaction

- show one question
- present 2-3 answer options
- allow custom text response
- user selects one option or enters their own answer
- user confirms once
- then continue generating or modifying the route

### Recommended layout

#### Header

- title: “Need one more detail”
- mode tag:
  - first generation
  - route modification

#### Intro card

- main question
- short reason why the system is asking

#### Step 1

- “Pick one option first”
- options shown as selectable cards or chips
- selected state should be obvious

#### Step 2

- “Confirm and continue”
- confirmation button placed clearly after the options

#### Custom answer section

- single-line or multi-line text field
- fallback when the suggested options are not enough

### Clarification page states

- default
- option selected
- custom text typed
- loading while resubmitting
- new clarification needed after submission

### Key interactions

- choose option
- edit custom answer
- confirm and continue
- back to previous page

## 5.3 Route Result Page

### Purpose

Show the generated route, let the user compare variants, explain the result, and modify it.

### Recommended layout

#### Top summary / hero

- route title
- one-line summary
- city
- budget
- total duration
- total distance
- number of stops

#### System understanding / diagnostics block

- show what the system understood from the user request
- show parse source / route capability / clarification info if needed
- keep this friendly and readable, not technical

#### Route option comparison

- show 3 route variants when available:
  - balanced
  - preference-focused
  - compact
- each option card should show:
  - strategy name
  - budget
  - duration
  - number of stops
  - short reason / fit label
- highlight the selected / recommended route

#### Route timeline / stop list

- each stop should show:
  - order number
  - POI name
  - category
  - time window
  - stay duration
  - price
  - rating
  - stop reason
- show travel segments between stops
- keep the timeline easy to scan

#### Map / route preview

- show a map preview or route preview card
- if real map is not available, show structured preview data gracefully

#### Quick modify section

- chips or quick buttons:
  - too far
  - lower budget
  - no queue
  - more relaxed
  - more photo spots
  - indoor only
- also keep a free-form modify input field

#### Bottom actions

- copy summary
- favorite/save route
- open knowledge explanation
- maybe share route

### Route result page states

- normal route
- clarification returned after modify
- no route found
- route updated after modification
- diagnostic available / unavailable

### Key interactions

- switch route variant
- inspect a stop
- modify route using quick chips or free text
- copy summary
- favorite route
- open explanation pages

## 5.4 Knowledge Explanation Page

### Purpose

Explain how the system understands user language and why it mapped certain words to tags or preferences.

### Recommended layout

#### Hero card

- “The system understands you first, then plans the route”
- show:
  - original input
  - system understanding summary

#### Common expression mapping

Show user-facing examples:

- photo / check-in / good-looking -> photo preference
- eat something good -> food preference
- no queue / don’t wait too long -> queue avoidance
- too far / too roundabout -> compact route preference
- indoor / rain / avoid getting wet -> rainy-day / indoor preference

#### Current route explanation

- explain the current route in plain language
- show current preferences recognized
- show warnings or limitations if any

#### How to adjust

- if the user wants:
  - more relaxed
  - cheaper
  - fewer queues
  - more photo spots
  - more indoor-friendly
- give short “try saying this” examples

### Key interactions

- read-only information
- maybe quick jump back to route modification

## 6. Shared Components

Stitch should design a reusable component system around these elements:

- city selector
- quick example card
- preference chip
- summary pill
- section card
- step card
- route option card
- route stop card
- timeline segment
- diagnostic card
- clarification option card
- bottom action bar
- loading overlay
- snackbar / toast

## 7. Suggested Content Tone

The copy should be:

- concise
- friendly
- confident
- not too technical
- not too playful
- easy to scan

Good example patterns:

- “You might prefer…”
- “Pick one to continue”
- “We understood your request as…”
- “Why this route fits”
- “Try saying it this way”

Avoid:

- too much technical jargon
- debugging terms in user-facing views
- long paragraphs
- over-explaining model internals

## 8. Responsive Behavior

### Mobile

- single-column stacked layout
- chips wrap naturally
- route stop cards full width
- bottom actions should be easy to reach

### Desktop

- more breathing room
- use two-column sections where helpful
- route comparison can sit beside preview/details
- keep the structure clean and card-based

## 9. What Stitch Should Produce

Stitch should design:

- a clean mobile-first route planning experience
- a strong hero/input experience
- a focused clarification interaction
- a route result page with comparison + timeline + actions
- a knowledge explanation page that is user-facing and approachable
- a consistent component library

## 10. What Not to Do

- do not make it look like a backend dashboard
- do not make every page look different
- do not overload users with model jargon
- do not use too many competing colors
- do not hide the main input behind extra steps
- do not force long question flows for clarification

## 11. Current Product Summary

The app currently supports:

- natural language route requests
- city selection
- preference chips
- example prompts
- lightweight clarification
- route generation
- route modification
- route comparison
- route explanation
- knowledge explanation
- map / route diagnostics
- copy / favorite route actions

## 12. Chat-Like But Not Chat-Only

The UX should feel conversational, but the product should not degrade into a pure chat app.

### What to keep conversational

- the initial request entry
- lightweight clarification
- route modification prompts
- explanation / rationale

### What should stay structured

- route comparison
- route timeline
- map preview
- diagnostics
- favorite / copy / share actions

### Design principle

Use chat-like entry to collect intent, then immediately convert the result into structured route cards and timeline views. The user should feel they are talking to the system, but the product should still look and behave like a planning workspace.

This should be reflected clearly in the UI.
