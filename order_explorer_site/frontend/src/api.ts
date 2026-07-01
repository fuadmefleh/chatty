import axios from 'axios';
import { getStoredApiKey } from './chattyApi';

const api = axios.create({
  baseURL: '/api/explorer',
});

api.interceptors.request.use((config) => {
  const key = getStoredApiKey();
  if (key) {
    config.headers['X-API-Key'] = key;
  }
  return config;
});

export interface Order {
  id: string;
  original_id: string;
  date: string;
  total: number;
  source: string;
  items_summary: string;
}

export interface Item {
  name: string;
  price: number;
  quantity: number;
  total_price: number;
  category: string;
  date: string;
  source: string;
  order_id?: string;
}

export const fetchOrders = async () => {
  const response = await api.get<Order[]>('/orders');
  return response.data;
};

export const fetchItems = async () => {
  const response = await api.get<Item[]>('/items');
  return response.data;
};

export const fetchItemHistory = async (itemName: string) => {
  const response = await api.get<Item[]>(`/items/${encodeURIComponent(itemName)}/history`);
  return response.data;
};

export const fetchOrderItems = async (orderId: string) => {
  const response = await api.get<Item[]>(`/orders/${orderId}/items`);
  return response.data;
};

export const fetchAllCategories = async () => {
  const response = await api.get<{ categories: string[] }>('/categories/list');
  return response.data.categories;
};

export const updateItemCategory = async (itemName: string, newCategory: string) => {
  const response = await api.patch<{ success: boolean; message: string }>('/items/category', {
    item_name: itemName,
    new_category: newCategory,
  });
  return response.data;
};

// ==================== Exercise Types ====================

export interface Exercise {
  id: number;
  name: string;
  category: string;
  muscle_group: string;
  description: string;
  video_url: string;
  is_bfs_core: boolean;
}

export interface WorkoutSession {
  id: number;
  program_id?: number;
  workout_date: string;
  workout_type: string;
  duration_minutes: number;
  notes: string;
  exercise_count?: number;
  total_volume?: number;
  sets?: WorkoutSet[];
}

export interface WorkoutSet {
  id: number;
  session_id: number;
  exercise_id: number;
  exercise_name?: string;
  category?: string;
  muscle_group?: string;
  set_number: number;
  reps: number;
  weight: number;
  rpe: number;
  notes: string;
}

export interface PersonalRecord {
  id: number;
  exercise_id: number;
  exercise_name: string;
  record_type: string;
  value: number;
  date_achieved: string;
  session_id?: number;
  notes: string;
}

export interface BodyMeasurement {
  id: number;
  measurement_date: string;
  weight?: number;
  body_fat_percentage?: number;
  chest?: number;
  waist?: number;
  hips?: number;
  arms?: number;
  thighs?: number;
  calves?: number;
  notes: string;
}

export interface ExerciseStats {
  total_workouts: number;
  total_sets: number;
  total_volume: number;
  last_workout_date: string;
  workouts_last_30_days: number;
}

export interface ProgressData {
  workout_date: string;
  max_weight: number;
  avg_weight: number;
  total_volume: number;
  max_reps: number;
}

// ==================== Exercise API Functions ====================

export const fetchExercises = async () => {
  const response = await api.get<Exercise[]>('/exercises');
  return response.data;
};

export const fetchExercise = async (exerciseId: number) => {
  const response = await api.get<Exercise>(`/exercises/${exerciseId}`);
  return response.data;
};

export const fetchExerciseHistory = async (exerciseId: number, limit: number = 20) => {
  const response = await api.get<WorkoutSet[]>(`/exercises/${exerciseId}/history?limit=${limit}`);
  return response.data;
};

export const fetchExerciseProgress = async (exerciseId: number, days: number = 90) => {
  const response = await api.get<ProgressData[]>(`/exercises/${exerciseId}/progress?days=${days}`);
  return response.data;
};

export const fetchWorkouts = async (limit: number = 10) => {
  const response = await api.get<WorkoutSession[]>(`/workouts?limit=${limit}`);
  return response.data;
};

export const fetchWorkoutDetails = async (sessionId: number) => {
  const response = await api.get<WorkoutSession>(`/workouts/${sessionId}`);
  return response.data;
};

export const createWorkout = async (workout: Omit<WorkoutSession, 'id' | 'exercise_count' | 'total_volume'>) => {
  const response = await api.post<{ id: number; message: string }>('/workouts', workout);
  return response.data;
};

export const addSetToWorkout = async (workoutSet: Omit<WorkoutSet, 'id' | 'exercise_name' | 'category' | 'muscle_group'>) => {
  const response = await api.post<{ id: number; message: string }>('/workouts/sets', workoutSet);
  return response.data;
};

export const deleteWorkout = async (sessionId: number) => {
  const response = await api.delete<{ message: string }>(`/workouts/${sessionId}`);
  return response.data;
};

export const fetchPersonalRecords = async (exerciseId?: number) => {
  const url = exerciseId ? `/personal-records?exercise_id=${exerciseId}` : '/personal-records';
  const response = await api.get<PersonalRecord[]>(url);
  return response.data;
};

export const addPersonalRecord = async (record: Omit<PersonalRecord, 'id' | 'exercise_name'>) => {
  const response = await api.post<{ id: number; message: string }>('/personal-records', record);
  return response.data;
};

export const fetchExerciseStats = async () => {
  const response = await api.get<ExerciseStats>('/exercise-stats');
  return response.data;
};

export const fetchBodyMeasurements = async (limit: number = 50) => {
  const response = await api.get<BodyMeasurement[]>(`/body-measurements?limit=${limit}`);
  return response.data;
};

export const addBodyMeasurement = async (measurement: Omit<BodyMeasurement, 'id'>) => {
  const response = await api.post<{ id: number; message: string }>('/body-measurements', measurement);
  return response.data;
};
