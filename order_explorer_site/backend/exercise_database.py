"""
Exercise tracking database for BFS (Bigger, Faster, Stronger) method
Handles workout programs, exercises, sets, and progress tracking
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

EXERCISE_DB = "/home/edgeworks-server/chatty/data/exercises/exercise_tracker.db"

def get_exercise_db_connection():
    """Create database connection and ensure schema exists"""
    os.makedirs(os.path.dirname(EXERCISE_DB), exist_ok=True)
    conn = sqlite3.connect(EXERCISE_DB)
    conn.row_factory = sqlite3.Row
    init_exercise_database(conn)
    return conn

def init_exercise_database(conn):
    """Initialize exercise tracking database schema"""
    cursor = conn.cursor()
    
    # Exercise types table (core BFS exercises + auxiliary)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL, -- 'core', 'auxiliary', 'speed', 'flexibility'
            muscle_group TEXT,
            description TEXT,
            video_url TEXT,
            is_bfs_core BOOLEAN DEFAULT 0
        )
    """)
    
    # Workout programs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            duration_weeks INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Workout sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER,
            workout_date DATE NOT NULL,
            workout_type TEXT, -- 'upper', 'lower', 'full', 'speed', 'flexibility'
            duration_minutes INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (program_id) REFERENCES programs (id)
        )
    """)
    
    # Sets and reps tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workout_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            set_number INTEGER NOT NULL,
            reps INTEGER,
            weight REAL,
            rpe REAL, -- Rate of Perceived Exertion (1-10)
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES workout_sessions (id),
            FOREIGN KEY (exercise_id) REFERENCES exercises (id)
        )
    """)
    
    # Personal records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personal_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            record_type TEXT NOT NULL, -- '1RM', '3RM', '5RM', '10RM', 'max_reps', 'max_volume'
            value REAL NOT NULL,
            date_achieved DATE NOT NULL,
            session_id INTEGER,
            notes TEXT,
            FOREIGN KEY (exercise_id) REFERENCES exercises (id),
            FOREIGN KEY (session_id) REFERENCES workout_sessions (id)
        )
    """)
    
    # Body measurements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS body_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_date DATE NOT NULL,
            weight REAL,
            body_fat_percentage REAL,
            chest REAL,
            waist REAL,
            hips REAL,
            arms REAL,
            thighs REAL,
            calves REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    
    # Insert BFS core exercises if not exists
    _insert_default_exercises(cursor, conn)

def _insert_default_exercises(cursor, conn):
    """Insert default BFS exercises"""
    bfs_core_exercises = [
        ('Squat', 'core', 'Legs', 'Back squat - king of exercises', '', 1),
        ('Bench Press', 'core', 'Chest', 'Flat barbell bench press', '', 1),
        ('Power Clean', 'core', 'Full Body', 'Olympic lift for explosive power', '', 1),
        ('Deadlift', 'core', 'Back/Legs', 'Conventional or sumo deadlift', '', 1),
        ('Hex Bar Deadlift', 'core', 'Back/Legs', 'Trap bar deadlift variation', '', 1),
    ]
    
    auxiliary_exercises = [
        ('Box Squat', 'auxiliary', 'Legs', 'Squat variation for power', '', 0),
        ('Front Squat', 'auxiliary', 'Legs', 'Quad-focused squat', '', 0),
        ('Incline Bench Press', 'auxiliary', 'Chest', 'Upper chest focus', '', 0),
        ('Military Press', 'auxiliary', 'Shoulders', 'Overhead barbell press', '', 0),
        ('Pull-ups', 'auxiliary', 'Back', 'Bodyweight back exercise', '', 0),
        ('Barbell Row', 'auxiliary', 'Back', 'Horizontal pulling movement', '', 0),
        ('Romanian Deadlift', 'auxiliary', 'Hamstrings', 'Hip hinge for hamstrings', '', 0),
        ('Lunges', 'auxiliary', 'Legs', 'Single leg exercise', '', 0),
        ('Dips', 'auxiliary', 'Chest/Triceps', 'Bodyweight pressing', '', 0),
        ('Leg Press', 'auxiliary', 'Legs', 'Machine-based leg exercise', '', 0),
    ]
    
    speed_exercises = [
        ('Sprint 40 Yard', 'speed', 'Full Body', '40 yard dash', '', 0),
        ('Sprint 100 Meter', 'speed', 'Full Body', '100 meter sprint', '', 0),
        ('Box Jumps', 'speed', 'Legs', 'Plyometric jump training', '', 0),
        ('Broad Jump', 'speed', 'Legs', 'Standing long jump', '', 0),
        ('Agility Ladder', 'speed', 'Full Body', 'Foot speed and coordination', '', 0),
    ]
    
    flexibility_exercises = [
        ('Hamstring Stretch', 'flexibility', 'Hamstrings', 'Static stretch', '', 0),
        ('Hip Flexor Stretch', 'flexibility', 'Hips', 'Static stretch', '', 0),
        ('Shoulder Stretch', 'flexibility', 'Shoulders', 'Static stretch', '', 0),
        ('Quad Stretch', 'flexibility', 'Quadriceps', 'Static stretch', '', 0),
        ('Foam Rolling', 'flexibility', 'Full Body', 'Myofascial release', '', 0),
    ]
    
    all_exercises = bfs_core_exercises + auxiliary_exercises + speed_exercises + flexibility_exercises
    
    for exercise in all_exercises:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO exercises (name, category, muscle_group, description, video_url, is_bfs_core)
                VALUES (?, ?, ?, ?, ?, ?)
            """, exercise)
        except sqlite3.IntegrityError:
            pass  # Exercise already exists
    
    conn.commit()

# ==================== CRUD Operations ====================

def get_all_exercises() -> List[Dict[str, Any]]:
    """Get all exercises"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exercises ORDER BY is_bfs_core DESC, category, name")
    exercises = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return exercises

def get_exercise_by_id(exercise_id: int) -> Optional[Dict[str, Any]]:
    """Get specific exercise by ID"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_workout_session(program_id: Optional[int], workout_date: str, 
                          workout_type: str, duration_minutes: int = 0, 
                          notes: str = "") -> int:
    """Create a new workout session"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workout_sessions (program_id, workout_date, workout_type, duration_minutes, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (program_id, workout_date, workout_type, duration_minutes, notes))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def add_set_to_session(session_id: int, exercise_id: int, set_number: int, 
                       reps: int, weight: float, rpe: float = 0, notes: str = "") -> int:
    """Add a set to a workout session"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workout_sets (session_id, exercise_id, set_number, reps, weight, rpe, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, exercise_id, set_number, reps, weight, rpe, notes))
    set_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return set_id

def get_recent_workouts(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent workout sessions"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ws.*, COUNT(DISTINCT wset.exercise_id) as exercise_count,
               SUM(wset.reps * wset.weight) as total_volume
        FROM workout_sessions ws
        LEFT JOIN workout_sets wset ON ws.id = wset.session_id
        GROUP BY ws.id
        ORDER BY ws.workout_date DESC, ws.created_at DESC
        LIMIT ?
    """, (limit,))
    workouts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return workouts

def get_workout_session_details(session_id: int) -> Dict[str, Any]:
    """Get detailed information about a workout session"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    
    # Get session info
    cursor.execute("SELECT * FROM workout_sessions WHERE id = ?", (session_id,))
    session = dict(cursor.fetchone())
    
    # Get all sets for this session with exercise names
    cursor.execute("""
        SELECT ws.*, e.name as exercise_name, e.category, e.muscle_group
        FROM workout_sets ws
        JOIN exercises e ON ws.exercise_id = e.id
        WHERE ws.session_id = ?
        ORDER BY e.name, ws.set_number
    """, (session_id,))
    sets = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    session['sets'] = sets
    return session

def get_exercise_history(exercise_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Get history of a specific exercise"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ws.workout_date, wset.*, e.name as exercise_name
        FROM workout_sets wset
        JOIN workout_sessions ws ON wset.session_id = ws.id
        JOIN exercises e ON wset.exercise_id = e.id
        WHERE wset.exercise_id = ?
        ORDER BY ws.workout_date DESC, wset.set_number
        LIMIT ?
    """, (exercise_id, limit))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

def get_personal_records(exercise_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get personal records, optionally filtered by exercise"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    
    if exercise_id:
        cursor.execute("""
            SELECT pr.*, e.name as exercise_name
            FROM personal_records pr
            JOIN exercises e ON pr.exercise_id = e.id
            WHERE pr.exercise_id = ?
            ORDER BY pr.date_achieved DESC
        """, (exercise_id,))
    else:
        cursor.execute("""
            SELECT pr.*, e.name as exercise_name
            FROM personal_records pr
            JOIN exercises e ON pr.exercise_id = e.id
            ORDER BY pr.date_achieved DESC
        """)
    
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def add_personal_record(exercise_id: int, record_type: str, value: float, 
                       date_achieved: str, session_id: Optional[int] = None, 
                       notes: str = "") -> int:
    """Add a personal record"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO personal_records (exercise_id, record_type, value, date_achieved, session_id, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (exercise_id, record_type, value, date_achieved, session_id, notes))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def get_exercise_stats() -> Dict[str, Any]:
    """Get overall exercise statistics"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    
    # Total workouts
    cursor.execute("SELECT COUNT(*) as total_workouts FROM workout_sessions")
    total_workouts = cursor.fetchone()['total_workouts']
    
    # Total sets
    cursor.execute("SELECT COUNT(*) as total_sets FROM workout_sets")
    total_sets = cursor.fetchone()['total_sets']
    
    # Total volume
    cursor.execute("SELECT SUM(reps * weight) as total_volume FROM workout_sets")
    total_volume = cursor.fetchone()['total_volume'] or 0
    
    # Most recent workout
    cursor.execute("SELECT workout_date FROM workout_sessions ORDER BY workout_date DESC LIMIT 1")
    row = cursor.fetchone()
    last_workout = row['workout_date'] if row else None
    
    # Workout frequency (last 30 days)
    cursor.execute("""
        SELECT COUNT(*) as workouts_last_30_days 
        FROM workout_sessions 
        WHERE workout_date >= date('now', '-30 days')
    """)
    workouts_last_30 = cursor.fetchone()['workouts_last_30_days']
    
    conn.close()
    
    return {
        'total_workouts': total_workouts,
        'total_sets': total_sets,
        'total_volume': round(total_volume, 2),
        'last_workout_date': last_workout,
        'workouts_last_30_days': workouts_last_30
    }

def get_progress_data(exercise_id: int, days: int = 90) -> List[Dict[str, Any]]:
    """Get progress data for an exercise over time"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            ws.workout_date,
            MAX(wset.weight) as max_weight,
            AVG(wset.weight) as avg_weight,
            SUM(wset.reps * wset.weight) as total_volume,
            MAX(wset.reps) as max_reps
        FROM workout_sets wset
        JOIN workout_sessions ws ON wset.session_id = ws.id
        WHERE wset.exercise_id = ?
        AND ws.workout_date >= date('now', '-' || ? || ' days')
        GROUP BY ws.workout_date
        ORDER BY ws.workout_date
    """, (exercise_id, days))
    
    progress = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return progress

def delete_workout_session(session_id: int) -> bool:
    """Delete a workout session and all its sets"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    
    # Delete sets first (foreign key constraint)
    cursor.execute("DELETE FROM workout_sets WHERE session_id = ?", (session_id,))
    
    # Delete session
    cursor.execute("DELETE FROM workout_sessions WHERE id = ?", (session_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_body_measurement(measurement_date: str, weight: Optional[float] = None,
                        body_fat_percentage: Optional[float] = None,
                        chest: Optional[float] = None, waist: Optional[float] = None,
                        hips: Optional[float] = None, arms: Optional[float] = None,
                        thighs: Optional[float] = None, calves: Optional[float] = None,
                        notes: str = "") -> int:
    """Add body measurements"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO body_measurements 
        (measurement_date, weight, body_fat_percentage, chest, waist, hips, arms, thighs, calves, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (measurement_date, weight, body_fat_percentage, chest, waist, hips, arms, thighs, calves, notes))
    measurement_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return measurement_id

def get_body_measurements(limit: int = 50) -> List[Dict[str, Any]]:
    """Get body measurements history"""
    conn = get_exercise_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM body_measurements 
        ORDER BY measurement_date DESC 
        LIMIT ?
    """, (limit,))
    measurements = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return measurements
