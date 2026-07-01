# Exercise Tracker - BFS Method

The Order Explorer site has been expanded into a **Lifestyle Site** with the addition of a comprehensive Exercise Tracker based on the **Bigger, Faster, Stronger (BFS)** training method.

## Overview

The Exercise Tracker helps you log workouts, track progress, and follow the proven BFS training principles used by athletes worldwide. The system includes tracking for strength training, speed work, and flexibility exercises.

## Features

### 1. Exercise Dashboard (`/exercise`)
- Overview of your training statistics
- Total workouts, sets, and volume
- Recent workout summary
- Quick actions to log workouts, view exercises, history, and progress
- Information about the BFS method and training principles

### 2. Exercise Library (`/exercise/exercises`)
- Complete database of exercises including:
  - **BFS Core Lifts**: Squat, Bench Press, Power Clean, Deadlift
  - **Auxiliary Exercises**: Supporting movements for strength and muscle development
  - **Speed/Agility**: Sprint work, plyometrics, and conditioning
  - **Flexibility**: Stretching and mobility work
- Filter by category and search by name or muscle group
- Detailed exercise information with descriptions

### 3. Workout Logger (`/exercise/workout-logger`)
- Log complete workout sessions
- Track workout details:
  - Date, type (upper/lower/full body/speed/flexibility)
  - Duration in minutes
  - Workout notes and observations
- Add sets for each exercise with:
  - Reps and weight
  - RPE (Rate of Perceived Exertion 1-10)
  - Set-specific notes
- Real-time workout summary with volume calculations
- Quick access to all exercises organized by type

### 4. Workout History (`/exercise/history`)
- View all past workouts organized by month
- Monthly statistics (workouts, exercises, total volume)
- Detailed workout information at a glance
- Delete workouts if needed
- Filter by number of recent workouts

### 5. Workout Details (`/exercise/workout/:id`)
- Complete breakdown of a specific workout
- Sets grouped by exercise
- Volume and RPE calculations
- Exercise-specific statistics

### 6. Progress Tracker (`/exercise/progress`)
- Visual progress charts using Recharts
- Track progress for any exercise over time:
  - Weight progression (max and average)
  - Volume progression
  - Rep progression
- Customizable time periods (30/60/90/180/365 days)
- Key statistics: max weight, avg weight, total volume, max reps, sessions

### 7. Exercise Details (`/exercise/exercise/:id`)
- Individual exercise page with complete history
- Personal records (1RM, 3RM, 5RM, etc.)
- Recent sets and performance
- Quick links to log workouts and view progress

## Database Schema

The exercise tracker uses SQLite with the following tables:

### `exercises`
- Exercise library with name, category, muscle group, description
- Marks BFS core lifts

### `workout_sessions`
- Individual workout sessions with date, type, duration, notes

### `workout_sets`
- Individual sets with exercise, reps, weight, RPE

### `personal_records`
- Track PRs with record type (1RM, 3RM, etc.), value, date

### `body_measurements`
- Track body composition and measurements over time

## API Endpoints

### Exercise Endpoints
- `GET /exercises` - Get all exercises
- `GET /exercises/{id}` - Get specific exercise
- `GET /exercises/{id}/history` - Get exercise history
- `GET /exercises/{id}/progress` - Get progress data

### Workout Endpoints
- `GET /workouts` - Get recent workouts
- `GET /workouts/{id}` - Get workout details
- `POST /workouts` - Create new workout
- `POST /workouts/sets` - Add set to workout
- `DELETE /workouts/{id}` - Delete workout

### Stats Endpoints
- `GET /exercise-stats` - Overall statistics
- `GET /personal-records` - Get personal records
- `POST /personal-records` - Add new PR
- `GET /body-measurements` - Get measurements
- `POST /body-measurements` - Add measurement

## BFS Training Method

The Bigger, Faster, Stronger program focuses on:

### Core Lifts
- **Squat**: King of exercises for lower body strength
- **Bench Press**: Upper body pressing strength
- **Power Clean**: Olympic lift for explosive power
- **Deadlift**: Total body strength and posterior chain

### Training Principles
1. **Progressive Overload**: Gradually increase weight and volume
2. **Proper Form**: Technique is paramount for safety and effectiveness
3. **Consistency**: Regular training for long-term results
4. **Recovery**: Adequate rest between sessions

### Common Set-Rep Schemes
- **3x3**: Heavy strength work
- **5x5**: Power and strength building
- **10-8-6**: Hypertrophy focus with increasing weight
- **3x5**: Volume work

## Getting Started

1. Navigate to the Exercise section using the 💪 Exercise link in the navbar
2. Explore the Exercise Library to familiarize yourself with available exercises
3. Log your first workout using the Workout Logger
4. Track your progress over time with the Progress Tracker
5. Set personal records and watch your strength grow!

## Tech Stack

**Backend:**
- FastAPI (Python)
- SQLite database
- exercise_database.py module for all exercise-related operations

**Frontend:**
- React + TypeScript
- React Router for navigation
- Recharts for progress visualization
- Tailwind CSS for styling

## Future Enhancements

Potential additions to consider:
- Training programs and templates
- Workout scheduling/calendar
- Rest timer during workouts
- Video exercise demonstrations
- Social features (share workouts, compare progress)
- Mobile app
- Exercise form check using AI/video analysis
- Nutrition tracking integration
