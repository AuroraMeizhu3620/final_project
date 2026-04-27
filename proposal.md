# Project Proposal
## What are you building? 
I am building a Flask web application for Babson students that helps early-career individuals discover and act on professional development opportunities. The app allows users to share career tips and turn them into structured, actionable task lists that others can adopt and track.

## Why?
Many students know their target industry but spend excessive time searching for opportunities or don’t realize which small actions can meaningfully improve their profile. This app solves that problem by centralizing peer-shared advice and transforming it into actionable steps, helping students move from passive research to active progress.

## MVP vs. Stretch Goals
### MVP:
A Flask web app where users can submit posts containing a title, description, and tags. An AI API will transform the post into a structured list of tasks. All posts are displayed in a feed. Users can select a post, start its task group, and track their progress using a checklist.

### Stretch Goals
- Career-based filtering and recommendations
More advanced tagging (industry + skill level)
- Gamification features (points, streaks)
- User accounts and personalized tracking
Admin-highlighted posts

## What don't you know yet?
- How to structure user-generated posts and task groups cleanly in Flask and how to save and update each user’s task progress 
- learn more about user authentication, recommendation logic
- how to prompt ChatGPT API to transform posts into actionable tasks with a consistent format