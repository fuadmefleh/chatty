import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchExercises, createWorkout, addSetToWorkout } from '../api';
import type { Exercise } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Spinner from '../components/ui/Spinner';
import FormField from '../components/ui/form/FormField';
import Input from '../components/ui/form/Input';
import Select from '../components/ui/form/Select';
import { useToast } from '../hooks/useToast';

interface WorkoutSet {
  exercise_id: number;
  exercise_name: string;
  set_number: number;
  reps: number;
  weight: number;
  rpe: number;
  notes: string;
}

const sectionTitle = 'mb-4 font-mono text-[13px] uppercase tracking-wider text-muted';
const textareaClass = 'w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors focus:border-signal resize-vertical';
const thClass = 'px-2.5 py-2 text-left font-mono text-[11px] uppercase text-muted';

export default function WorkoutLogger() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [workoutDate, setWorkoutDate] = useState(new Date().toISOString().split('T')[0]);
  const [workoutType, setWorkoutType] = useState('upper');
  const [duration, setDuration] = useState(60);
  const [workoutNotes, setWorkoutNotes] = useState('');

  const [selectedExercise, setSelectedExercise] = useState<number | null>(null);
  const [sets, setSets] = useState<WorkoutSet[]>([]);

  const [newSetReps, setNewSetReps] = useState(5);
  const [newSetWeight, setNewSetWeight] = useState(0);
  const [newSetRpe, setNewSetRpe] = useState(7);
  const [newSetNotes, setNewSetNotes] = useState('');

  useEffect(() => {
    const loadExercises = async () => {
      try {
        const data = await fetchExercises();
        setExercises(data);
      } catch (error) {
        console.error('Error loading exercises:', error);
      } finally {
        setLoading(false);
      }
    };

    loadExercises();
  }, []);

  const addSet = () => {
    if (!selectedExercise) {
      showToast('Please select an exercise', 'amber');
      return;
    }

    const exercise = exercises.find(e => e.id === selectedExercise);
    if (!exercise) return;

    const existingSetsForExercise = sets.filter(s => s.exercise_id === selectedExercise).length;
    const setNumber = existingSetsForExercise + 1;

    const newSet: WorkoutSet = {
      exercise_id: selectedExercise,
      exercise_name: exercise.name,
      set_number: setNumber,
      reps: newSetReps,
      weight: newSetWeight,
      rpe: newSetRpe,
      notes: newSetNotes
    };

    setSets([...sets, newSet]);

    setNewSetReps(5);
    setNewSetWeight(newSet.weight);
    setNewSetRpe(7);
    setNewSetNotes('');
  };

  const removeSet = (index: number) => {
    setSets(sets.filter((_, i) => i !== index));
  };

  const saveWorkout = async () => {
    if (sets.length === 0) {
      showToast('Please add at least one set', 'amber');
      return;
    }

    setSaving(true);
    try {
      const workoutResponse = await createWorkout({
        workout_date: workoutDate,
        workout_type: workoutType,
        duration_minutes: duration,
        notes: workoutNotes
      });

      const sessionId = workoutResponse.id;

      for (const set of sets) {
        await addSetToWorkout({
          session_id: sessionId,
          exercise_id: set.exercise_id,
          set_number: set.set_number,
          reps: set.reps,
          weight: set.weight,
          rpe: set.rpe,
          notes: set.notes
        });
      }

      showToast('Workout saved successfully', 'green');
      navigate(`/exercise/workout/${sessionId}`);
    } catch (error) {
      console.error('Error saving workout:', error);
      showToast('Failed to save workout', 'red');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto flex max-w-[1000px] items-center justify-center px-4 py-16 md:px-6">
        <Spinner label="Loading…" />
      </div>
    );
  }

  const groupedSets = sets.reduce((acc, set) => {
    if (!acc[set.exercise_name]) {
      acc[set.exercise_name] = [];
    }
    acc[set.exercise_name].push(set);
    return acc;
  }, {} as Record<string, WorkoutSet[]>);

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--alert-red)" title="Log workout" />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Left Column - Workout Details */}
        <div className="flex flex-col gap-5">
          <Card>
            <h2 className={sectionTitle}>Workout details</h2>

            <div className="flex flex-col gap-3.5">
              <FormField label="Date" htmlFor="workout-date">
                <Input id="workout-date" type="date" value={workoutDate} onChange={(e) => setWorkoutDate(e.target.value)} />
              </FormField>

              <FormField label="Type" htmlFor="workout-type">
                <Select id="workout-type" value={workoutType} onChange={(e) => setWorkoutType(e.target.value)}>
                  <option value="upper">Upper body</option>
                  <option value="lower">Lower body</option>
                  <option value="full">Full body</option>
                  <option value="speed">Speed/Agility</option>
                  <option value="flexibility">Flexibility</option>
                </Select>
              </FormField>

              <FormField label="Duration (minutes)" htmlFor="workout-duration">
                <Input id="workout-duration" type="number" value={duration} onChange={(e) => setDuration(parseInt(e.target.value))} min="0" />
              </FormField>

              <FormField label="Notes" htmlFor="workout-notes">
                <textarea
                  id="workout-notes"
                  value={workoutNotes}
                  onChange={(e) => setWorkoutNotes(e.target.value)}
                  className={textareaClass}
                  rows={3}
                  placeholder="How did you feel? Any observations?"
                />
              </FormField>
            </div>
          </Card>

          {/* Add Set Form */}
          <Card>
            <h2 className={sectionTitle}>Add set</h2>

            <div className="flex flex-col gap-3.5">
              <FormField label="Exercise" htmlFor="set-exercise">
                <Select id="set-exercise" value={selectedExercise || ''} onChange={(e) => setSelectedExercise(parseInt(e.target.value))}>
                  <option value="">Select exercise…</option>
                  <optgroup label="BFS core lifts">
                    {exercises.filter(e => e.is_bfs_core).map(exercise => (
                      <option key={exercise.id} value={exercise.id}>{exercise.name}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Auxiliary exercises">
                    {exercises.filter(e => !e.is_bfs_core && e.category === 'auxiliary').map(exercise => (
                      <option key={exercise.id} value={exercise.id}>{exercise.name}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Other">
                    {exercises.filter(e => !e.is_bfs_core && e.category !== 'auxiliary').map(exercise => (
                      <option key={exercise.id} value={exercise.id}>{exercise.name}</option>
                    ))}
                  </optgroup>
                </Select>
              </FormField>

              <div className="grid grid-cols-2 gap-3">
                <FormField label="Reps" htmlFor="set-reps">
                  <Input id="set-reps" type="number" value={newSetReps} onChange={(e) => setNewSetReps(parseInt(e.target.value))} min="1" />
                </FormField>
                <FormField label="Weight (lbs)" htmlFor="set-weight">
                  <Input id="set-weight" type="number" value={newSetWeight} onChange={(e) => setNewSetWeight(parseFloat(e.target.value))} min="0" step="5" />
                </FormField>
              </div>

              <FormField label="RPE (perceived exertion, 1–10)" htmlFor="set-rpe">
                <Input id="set-rpe" type="number" value={newSetRpe} onChange={(e) => setNewSetRpe(parseFloat(e.target.value))} min="1" max="10" step="0.5" />
              </FormField>

              <FormField label="Set notes" htmlFor="set-notes">
                <Input id="set-notes" type="text" value={newSetNotes} onChange={(e) => setNewSetNotes(e.target.value)} placeholder="Optional notes" />
              </FormField>

              <button onClick={addSet} className="h-10 w-full rounded-lg bg-alert-red text-sm font-bold text-white">
                Add set
              </button>
            </div>
          </Card>
        </div>

        {/* Right Column - Current Workout */}
        <div className="min-w-0 lg:col-span-2">
          <Card>
            <h2 className={sectionTitle}>Current workout</h2>

            {sets.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted">
                No sets added yet. Add your first set to begin.
              </div>
            ) : (
              <div className="flex flex-col gap-5">
                {Object.entries(groupedSets).map(([exerciseName, exerciseSets]) => (
                  <div key={exerciseName} className="rounded-lg border border-line p-3.5">
                    <h3 className="mb-3 text-[14.5px] font-bold text-ink">{exerciseName}</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full border-collapse">
                        <thead>
                          <tr className="bg-surface-dim">
                            <th className={thClass}>Set</th>
                            <th className={thClass}>Reps</th>
                            <th className={thClass}>Weight</th>
                            <th className={thClass}>RPE</th>
                            <th className={thClass}>Volume</th>
                            <th className={thClass}>Notes</th>
                            <th className={`${thClass} text-center`}>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {exerciseSets.map((set, index) => {
                            const globalIndex = sets.findIndex(s =>
                              s.exercise_id === set.exercise_id && s.set_number === set.set_number
                            );
                            return (
                              <tr key={index} className="border-t border-line">
                                <td className="px-2.5 py-2 text-ink-dim">{set.set_number}</td>
                                <td className="px-2.5 py-2 text-ink-dim">{set.reps}</td>
                                <td className="px-2.5 py-2 text-ink-dim">{set.weight} lbs</td>
                                <td className="px-2.5 py-2 text-ink-dim">{set.rpe}</td>
                                <td className="px-2.5 py-2 font-mono font-bold text-alert-red">
                                  {(set.reps * set.weight).toFixed(0)} lbs
                                </td>
                                <td className="px-2.5 py-2 text-xs text-muted">{set.notes}</td>
                                <td className="px-2.5 py-2 text-center">
                                  <button onClick={() => removeSet(globalIndex)} className="rounded-md border border-line px-2.5 py-1 text-xs text-alert-red">
                                    Remove
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}

                {/* Workout Summary */}
                <div className="border-t border-line pt-4">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div>
                      <div className="font-mono text-xl font-bold text-alert-red">{sets.length}</div>
                      <div className="text-xs text-muted">Total sets</div>
                    </div>
                    <div>
                      <div className="font-mono text-xl font-bold text-alert-amber">{Object.keys(groupedSets).length}</div>
                      <div className="text-xs text-muted">Exercises</div>
                    </div>
                    <div>
                      <div className="font-mono text-xl font-bold text-signal">
                        {sets.reduce((sum, set) => sum + (set.reps * set.weight), 0).toFixed(0)}
                      </div>
                      <div className="text-xs text-muted">Total volume (lbs)</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={saveWorkout}
                  disabled={saving}
                  className="h-11 w-full rounded-lg bg-alert-green text-[15px] font-bold text-white disabled:opacity-60"
                >
                  {saving ? 'Saving…' : 'Save workout'}
                </button>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
