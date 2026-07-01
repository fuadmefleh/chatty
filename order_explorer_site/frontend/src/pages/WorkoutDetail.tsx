import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { fetchWorkoutDetails } from '../api';
import type { WorkoutSession, WorkoutSet } from '../api';
import Card from '../components/ui/Card';

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };
const thStyle: React.CSSProperties = { padding: '10px 16px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const rpeTone = (rpe: number): { bg: string; fg: string } => {
  if (rpe >= 9) return { bg: 'rgba(216, 96, 63, 0.18)', fg: 'var(--stamp-ember)' };
  if (rpe >= 7) return { bg: 'rgba(200, 155, 60, 0.18)', fg: 'var(--stamp-gold)' };
  return { bg: 'rgba(110, 168, 122, 0.18)', fg: 'var(--success)' };
};

export default function WorkoutDetail() {
  const { id } = useParams<{ id: string }>();
  const [workout, setWorkout] = useState<WorkoutSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadWorkout = async () => {
      if (!id) return;

      try {
        const data = await fetchWorkoutDetails(parseInt(id));
        setWorkout(data);
      } catch (error) {
        console.error('Error loading workout:', error);
      } finally {
        setLoading(false);
      }
    };

    loadWorkout();
  }, [id]);

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  if (!workout) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Workout not found</div>;
  }

  const groupedSets = (workout.sets || []).reduce((acc, set) => {
    const key = set.exercise_name || 'Unknown';
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(set);
    return acc;
  }, {} as Record<string, WorkoutSet[]>);

  const totalVolume = (workout.sets || []).reduce(
    (sum, set) => sum + (set.reps * set.weight),
    0
  );

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--stamp-ember)', marginBottom: 6 }}>
          Training / Exercise
        </div>
        <h1 style={{ fontSize: 26, marginBottom: 6 }}>Workout details</h1>
        <div style={{ color: 'var(--muted)', fontSize: 14 }}>
          {new Date(workout.workout_date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        </div>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '14px', marginBottom: '28px' }}>
        <Card>
          <div style={statLabel}>Workout type</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--stamp-ember)', marginTop: 8, textTransform: 'capitalize' }}>{workout.workout_type}</div>
        </Card>
        <Card>
          <div style={statLabel}>Duration</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)', marginTop: 8 }}>
            {workout.duration_minutes > 0 ? `${workout.duration_minutes} min` : '—'}
          </div>
        </Card>
        <Card>
          <div style={statLabel}>Total volume</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)', marginTop: 8 }}>{totalVolume.toLocaleString()} lbs</div>
        </Card>
        <Card>
          <div style={statLabel}>Exercises</div>
          <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)', marginTop: 8 }}>{Object.keys(groupedSets).length}</div>
        </Card>
      </div>

      {/* Notes */}
      {workout.notes && (
        <Card style={{ marginBottom: '28px', borderLeft: '3px solid var(--stamp-teal)' }}>
          <div style={{ fontWeight: 700, color: 'var(--stamp-teal)', marginBottom: 4, fontSize: 13 }}>Workout notes</div>
          <div style={{ color: 'var(--paper-dim)', fontSize: 13.5 }}>{workout.notes}</div>
        </Card>
      )}

      {/* Exercises and Sets */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {Object.entries(groupedSets).map(([exerciseName, sets]) => {
          const exerciseVolume = sets.reduce((sum, set) => sum + (set.reps * set.weight), 0);
          const avgRpe = sets.reduce((sum, set) => sum + set.rpe, 0) / sets.length;

          return (
            <div key={exerciseName} style={{ border: '1px solid var(--ink-700)', borderRadius: 10, overflow: 'hidden' }}>
              <div style={{ background: 'var(--ink-800)', borderBottom: '1px solid var(--ink-700)', padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h2 style={{ fontSize: 17, color: 'var(--paper)' }}>{exerciseName}</h2>
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                      {sets[0].category && `${sets[0].category} · `}{sets[0].muscle_group}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{sets.length} sets</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>{exerciseVolume.toLocaleString()} lbs · RPE {avgRpe.toFixed(1)}</div>
                  </div>
                </div>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--ink-750)' }}>
                      <th style={thStyle}>Set</th>
                      <th style={thStyle}>Reps</th>
                      <th style={thStyle}>Weight</th>
                      <th style={thStyle}>Volume</th>
                      <th style={thStyle}>RPE</th>
                      <th style={thStyle}>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sets.map((set, index) => {
                      const tone = rpeTone(set.rpe);
                      return (
                        <tr key={index} style={{ borderTop: '1px solid var(--ink-700)' }}>
                          <td style={{ padding: '11px 16px', whiteSpace: 'nowrap', fontWeight: 700, color: 'var(--paper)' }}>{set.set_number}</td>
                          <td style={{ padding: '11px 16px', whiteSpace: 'nowrap', color: 'var(--paper-dim)' }}>{set.reps}</td>
                          <td style={{ padding: '11px 16px', whiteSpace: 'nowrap', color: 'var(--paper-dim)' }}>{set.weight} lbs</td>
                          <td style={{ padding: '11px 16px', whiteSpace: 'nowrap', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>
                            {(set.reps * set.weight).toFixed(0)} lbs
                          </td>
                          <td style={{ padding: '11px 16px', whiteSpace: 'nowrap' }}>
                            <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 700, borderRadius: 6, background: tone.bg, color: tone.fg }}>{set.rpe}</span>
                          </td>
                          <td style={{ padding: '11px 16px', fontSize: 12.5, color: 'var(--muted)' }}>{set.notes || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: '2px solid var(--ink-700)', background: 'var(--ink-800)' }}>
                      <td style={{ padding: '11px 16px', fontWeight: 700, color: 'var(--paper)' }}>Total</td>
                      <td style={{ padding: '11px 16px', fontWeight: 700, color: 'var(--paper)' }}>{sets.reduce((sum, s) => sum + s.reps, 0)}</td>
                      <td style={{ padding: '11px 16px' }}></td>
                      <td style={{ padding: '11px 16px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>{exerciseVolume.toLocaleString()} lbs</td>
                      <td style={{ padding: '11px 16px', fontWeight: 700, color: 'var(--paper)' }}>Avg {avgRpe.toFixed(1)}</td>
                      <td style={{ padding: '11px 16px' }}></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
