import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchExercises, createWorkout, addSetToWorkout } from '../api';
import type { Exercise } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

interface WorkoutSet {
  exercise_id: number;
  exercise_name: string;
  set_number: number;
  reps: number;
  weight: number;
  rpe: number;
  notes: string;
}

const fieldLabel: React.CSSProperties = { display: 'block', marginBottom: '6px', fontSize: '12px', fontWeight: 600, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' };
const fieldInput: React.CSSProperties = { width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 14 };
const thStyle: React.CSSProperties = { padding: '8px 10px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' };

export default function WorkoutLogger() {
  const navigate = useNavigate();
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
      alert('Please select an exercise');
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
      alert('Please add at least one set');
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

      alert('Workout saved successfully!');
      navigate(`/exercise/workout/${sessionId}`);
    } catch (error) {
      console.error('Error saving workout:', error);
      alert('Failed to save workout');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  const groupedSets = sets.reduce((acc, set) => {
    if (!acc[set.exercise_name]) {
      acc[set.exercise_name] = [];
    }
    acc[set.exercise_name].push(set);
    return acc;
  }, {} as Record<string, WorkoutSet[]>);

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--stamp-ember)" title="Log workout" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px', alignItems: 'start' }}>
        {/* Left Column - Workout Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <Card>
            <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Workout details</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={fieldLabel}>Date</label>
                <input type="date" value={workoutDate} onChange={(e) => setWorkoutDate(e.target.value)} style={fieldInput} />
              </div>

              <div>
                <label style={fieldLabel}>Type</label>
                <select value={workoutType} onChange={(e) => setWorkoutType(e.target.value)} style={fieldInput}>
                  <option value="upper">Upper body</option>
                  <option value="lower">Lower body</option>
                  <option value="full">Full body</option>
                  <option value="speed">Speed/Agility</option>
                  <option value="flexibility">Flexibility</option>
                </select>
              </div>

              <div>
                <label style={fieldLabel}>Duration (minutes)</label>
                <input type="number" value={duration} onChange={(e) => setDuration(parseInt(e.target.value))} style={fieldInput} min="0" />
              </div>

              <div>
                <label style={fieldLabel}>Notes</label>
                <textarea value={workoutNotes} onChange={(e) => setWorkoutNotes(e.target.value)} style={{ ...fieldInput, resize: 'vertical' }} rows={3} placeholder="How did you feel? Any observations?" />
              </div>
            </div>
          </Card>

          {/* Add Set Form */}
          <Card>
            <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Add set</h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={fieldLabel}>Exercise</label>
                <select value={selectedExercise || ''} onChange={(e) => setSelectedExercise(parseInt(e.target.value))} style={fieldInput}>
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
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={fieldLabel}>Reps</label>
                  <input type="number" value={newSetReps} onChange={(e) => setNewSetReps(parseInt(e.target.value))} style={fieldInput} min="1" />
                </div>
                <div>
                  <label style={fieldLabel}>Weight (lbs)</label>
                  <input type="number" value={newSetWeight} onChange={(e) => setNewSetWeight(parseFloat(e.target.value))} style={fieldInput} min="0" step="5" />
                </div>
              </div>

              <div>
                <label style={fieldLabel}>RPE (perceived exertion, 1–10)</label>
                <input type="number" value={newSetRpe} onChange={(e) => setNewSetRpe(parseFloat(e.target.value))} style={fieldInput} min="1" max="10" step="0.5" />
              </div>

              <div>
                <label style={fieldLabel}>Set notes</label>
                <input type="text" value={newSetNotes} onChange={(e) => setNewSetNotes(e.target.value)} style={fieldInput} placeholder="Optional notes" />
              </div>

              <button onClick={addSet} style={{ width: '100%', background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '11px', fontWeight: 700, fontSize: 14 }}>
                Add set
              </button>
            </div>
          </Card>
        </div>

        {/* Right Column - Current Workout */}
        <div style={{ gridColumn: 'span 2', minWidth: 0 }}>
          <Card>
            <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Current workout</h2>

            {sets.length === 0 ? (
              <div style={{ color: 'var(--muted)', textAlign: 'center', padding: '40px 0' }}>
                No sets added yet. Add your first set to begin.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {Object.entries(groupedSets).map(([exerciseName, exerciseSets]) => (
                  <div key={exerciseName} style={{ border: '1px solid var(--ink-700)', borderRadius: 8, padding: 14 }}>
                    <h3 style={{ fontWeight: 700, fontSize: 14.5, color: 'var(--paper)', marginBottom: 12 }}>{exerciseName}</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'var(--ink-750)' }}>
                            <th style={thStyle}>Set</th>
                            <th style={thStyle}>Reps</th>
                            <th style={thStyle}>Weight</th>
                            <th style={thStyle}>RPE</th>
                            <th style={thStyle}>Volume</th>
                            <th style={thStyle}>Notes</th>
                            <th style={{ ...thStyle, textAlign: 'center' }}>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {exerciseSets.map((set, index) => {
                            const globalIndex = sets.findIndex(s =>
                              s.exercise_id === set.exercise_id && s.set_number === set.set_number
                            );
                            return (
                              <tr key={index} style={{ borderTop: '1px solid var(--ink-700)' }}>
                                <td style={{ padding: '8px 10px', color: 'var(--paper-dim)' }}>{set.set_number}</td>
                                <td style={{ padding: '8px 10px', color: 'var(--paper-dim)' }}>{set.reps}</td>
                                <td style={{ padding: '8px 10px', color: 'var(--paper-dim)' }}>{set.weight} lbs</td>
                                <td style={{ padding: '8px 10px', color: 'var(--paper-dim)' }}>{set.rpe}</td>
                                <td style={{ padding: '8px 10px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>
                                  {(set.reps * set.weight).toFixed(0)} lbs
                                </td>
                                <td style={{ padding: '8px 10px', fontSize: 12, color: 'var(--muted)' }}>{set.notes}</td>
                                <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                                  <button onClick={() => removeSet(globalIndex)} style={{ background: 'transparent', color: 'var(--danger)', padding: '4px 10px', fontSize: 12, border: '1px solid var(--ink-600)' }}>
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
                <div style={{ borderTop: '1px solid var(--ink-700)', paddingTop: 16 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, textAlign: 'center' }}>
                    <div>
                      <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{sets.length}</div>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>Total sets</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)' }}>{Object.keys(groupedSets).length}</div>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>Exercises</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '22px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)' }}>
                        {sets.reduce((sum, set) => sum + (set.reps * set.weight), 0).toFixed(0)}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>Total volume (lbs)</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={saveWorkout}
                  disabled={saving}
                  style={{ width: '100%', background: 'var(--success)', color: 'var(--ink-900)', padding: '13px', fontWeight: 700, fontSize: 15, opacity: saving ? 0.6 : 1 }}
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
