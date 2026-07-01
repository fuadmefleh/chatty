import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv

# Load the repo-root .env regardless of the process's cwd
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.getenv("CHATTY_WEB_API_KEY", "changeme")


async def require_api_key(x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
from database import (
    get_all_orders, get_all_items, get_item_history, get_order_items, 
    get_dashboard_stats, get_monthly_breakdown, get_yearly_breakdown, get_category_analysis,
    get_vendor_analysis, search_items, get_recurring_items, get_budget_summary,
    get_all_categories, update_item_category
)
from exercise_database import (
    get_all_exercises, get_exercise_by_id, create_workout_session, add_set_to_session,
    get_recent_workouts, get_workout_session_details, get_exercise_history,
    get_personal_records, add_personal_record, get_exercise_stats, get_progress_data,
    delete_workout_session, add_body_measurement, get_body_measurements
)

app = FastAPI(title="Order Explorer API", dependencies=[Depends(require_api_key)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Order(BaseModel):
    id: str
    original_id: str
    date: Optional[str] = None
    total: Optional[float] = 0.0
    source: str
    items_summary: Optional[str] = None

class Item(BaseModel):
    name: Optional[str]
    price: Optional[float]
    quantity: Optional[int]
    total_price: Optional[float]
    category: Optional[str]
    date: Optional[str]
    source: str
    order_id: str

class UpdateCategoryRequest(BaseModel):
    item_name: str
    new_category: str

# Exercise-related models
class WorkoutSessionCreate(BaseModel):
    program_id: Optional[int] = None
    workout_date: str
    workout_type: str
    duration_minutes: int = 0
    notes: str = ""

class WorkoutSetCreate(BaseModel):
    session_id: int
    exercise_id: int
    set_number: int
    reps: int
    weight: float
    rpe: float = 0
    notes: str = ""

class PersonalRecordCreate(BaseModel):
    exercise_id: int
    record_type: str
    value: float
    date_achieved: str
    session_id: Optional[int] = None
    notes: str = ""

class BodyMeasurementCreate(BaseModel):
    measurement_date: str
    weight: Optional[float] = None
    body_fat_percentage: Optional[float] = None
    chest: Optional[float] = None
    waist: Optional[float] = None
    hips: Optional[float] = None
    arms: Optional[float] = None
    thighs: Optional[float] = None
    calves: Optional[float] = None
    notes: str = ""

@app.get("/orders", response_model=List[Order])
def read_orders():
    return get_all_orders()

@app.get("/items", response_model=List[Item])
def read_items():
    return get_all_items()

@app.get("/items/{item_name}/history", response_model=List[Item])
def read_item_history(item_name: str):
    return get_item_history(item_name)

@app.get("/orders/{order_id}/items", response_model=List[Item])
def read_order_items(order_id: str):
    return get_order_items(order_id)

@app.get("/dashboard")
def read_dashboard_stats():
    return get_dashboard_stats()

@app.get("/months")
def read_monthly_breakdown():
    return get_monthly_breakdown()

@app.get("/years")
def read_yearly_breakdown():
    return get_yearly_breakdown()

@app.get("/categories")
def read_category_analysis():
    return get_category_analysis()

@app.get("/vendors")
def read_vendor_analysis():
    return get_vendor_analysis()

@app.get("/search")
def search_for_items(
    q: str = Query(default='', description="Search query"),
    category: Optional[str] = None,
    source: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    return search_items(q, category, source, min_price, max_price)

@app.get("/recurring")
def read_recurring_items():
    return get_recurring_items()

@app.get("/budget")
def read_budget_summary(monthly_limit: Optional[float] = None):
    return get_budget_summary(monthly_limit)

@app.get("/categories/list")
def read_all_categories():
    return {"categories": get_all_categories()}

@app.patch("/items/category")
def update_category(request: UpdateCategoryRequest):
    print(f"Received update request: item_name={request.item_name}, new_category={request.new_category}")
    success = update_item_category(request.item_name, request.new_category)
    if success:
        return {"success": True, "message": "Category updated for all instances of this item"}
    else:
        raise HTTPException(status_code=400, detail="Failed to update category")

# ==================== Exercise Endpoints ====================

@app.get("/exercises")
def read_exercises():
    """Get all available exercises"""
    return get_all_exercises()

@app.get("/exercises/{exercise_id}")
def read_exercise(exercise_id: int):
    """Get specific exercise by ID"""
    exercise = get_exercise_by_id(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise

@app.get("/exercises/{exercise_id}/history")
def read_exercise_history_endpoint(exercise_id: int, limit: int = 20):
    """Get history of sets/workouts for a specific exercise"""
    return get_exercise_history(exercise_id, limit)

@app.get("/exercises/{exercise_id}/progress")
def read_exercise_progress(exercise_id: int, days: int = 90):
    """Get progress data for an exercise over time"""
    return get_progress_data(exercise_id, days)

@app.get("/workouts")
def read_workouts(limit: int = 10):
    """Get recent workout sessions"""
    return get_recent_workouts(limit)

@app.get("/workouts/{session_id}")
def read_workout_details(session_id: int):
    """Get detailed information about a workout session"""
    try:
        return get_workout_session_details(session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Workout session not found: {str(e)}")

@app.post("/workouts")
def create_workout(workout: WorkoutSessionCreate):
    """Create a new workout session"""
    try:
        session_id = create_workout_session(
            workout.program_id,
            workout.workout_date,
            workout.workout_type,
            workout.duration_minutes,
            workout.notes
        )
        return {"id": session_id, "message": "Workout session created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/workouts/sets")
def create_workout_set(workout_set: WorkoutSetCreate):
    """Add a set to a workout session"""
    try:
        set_id = add_set_to_session(
            workout_set.session_id,
            workout_set.exercise_id,
            workout_set.set_number,
            workout_set.reps,
            workout_set.weight,
            workout_set.rpe,
            workout_set.notes
        )
        return {"id": set_id, "message": "Set added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/workouts/{session_id}")
def delete_workout(session_id: int):
    """Delete a workout session"""
    success = delete_workout_session(session_id)
    if success:
        return {"message": "Workout session deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Workout session not found")

@app.get("/personal-records")
def read_personal_records(exercise_id: Optional[int] = None):
    """Get personal records, optionally filtered by exercise"""
    return get_personal_records(exercise_id)

@app.post("/personal-records")
def create_personal_record(record: PersonalRecordCreate):
    """Add a personal record"""
    try:
        record_id = add_personal_record(
            record.exercise_id,
            record.record_type,
            record.value,
            record.date_achieved,
            record.session_id,
            record.notes
        )
        return {"id": record_id, "message": "Personal record added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/exercise-stats")
def read_exercise_stats():
    """Get overall exercise statistics"""
    return get_exercise_stats()

@app.get("/body-measurements")
def read_body_measurements(limit: int = 50):
    """Get body measurements history"""
    return get_body_measurements(limit)

@app.post("/body-measurements")
def create_body_measurement(measurement: BodyMeasurementCreate):
    """Add body measurements"""
    try:
        measurement_id = add_body_measurement(
            measurement.measurement_date,
            measurement.weight,
            measurement.body_fat_percentage,
            measurement.chest,
            measurement.waist,
            measurement.hips,
            measurement.arms,
            measurement.thighs,
            measurement.calves,
            measurement.notes
        )
        return {"id": measurement_id, "message": "Body measurement added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return get_category_analysis()

@app.get("/vendors")
def read_vendor_analysis():
    return get_vendor_analysis()

@app.get("/search")
def search_for_items(
    q: str = Query(default='', description="Search query"),
    category: Optional[str] = None,
    source: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    return search_items(q, category, source, min_price, max_price)

@app.get("/recurring")
def read_recurring_items():
    return get_recurring_items()

@app.get("/budget")
def read_budget_summary(monthly_limit: Optional[float] = None):
    return get_budget_summary(monthly_limit)

@app.get("/categories/list")
def read_all_categories():
    return {"categories": get_all_categories()}

@app.patch("/items/category")
def update_category(request: UpdateCategoryRequest):
    print(f"Received update request: item_name={request.item_name}, new_category={request.new_category}")
    success = update_item_category(request.item_name, request.new_category)
    if success:
        return {"success": True, "message": "Category updated for all instances of this item"}
    else:
        raise HTTPException(status_code=400, detail="Failed to update category")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8015, reload=True)
