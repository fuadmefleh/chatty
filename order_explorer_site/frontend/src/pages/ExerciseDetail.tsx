import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchExercise, fetchExerciseHistory, fetchPersonalRecords } from '../api';
import type { Exercise, WorkoutSet, PersonalRecord } from '../api';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';

// The history endpoint joins in the session's workout_date, which the shared WorkoutSet type doesn't declare.
type HistorySet = WorkoutSet & { workout_date: string };

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const rpeTone = (rpe: number): { bg: string; fg: string } => {
  if (rpe >= 9) return { bg: 'rgba(216, 96, 63, 0.18)', fg: 'var(--stamp-ember)' };
  if (rpe >= 7) return { bg: 'rgba(200, 155, 60, 0.18)', fg: 'var(--stamp-gold)' };
  return { bg: 'rgba(110, 168, 122, 0.18)', fg: 'var(--success)' };
};

export default function ExerciseDetail() {
  const { id } = useParams<{ id: string }>();
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [history, setHistory] = useState<HistorySet[]>([]);
  const [records, setRecords] = useState<PersonalRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      if (!id) return;

      try {
        const exerciseId = parseInt(id);
        const [exerciseData, historyData, recordsData] = await Promise.all([
          fetchExercise(exerciseId),
          fetchExerciseHistory(exerciseId, 20),
          fetchPersonalRecords(exerciseId)
        ]);

        setExercise(exerciseData);
        setHistory(historyData as HistorySet[]);
        setRecords(recordsData);
      } catch (error) {
        console.error('Error loading exercise details:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [id]);

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  if (!exercise) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Exercise not found</div>;
  }

  const maxWeight = history.length > 0 ? Math.max(...history.map(h => h.weight)) : 0;
  const totalSets = history.length;
  const totalVolume = history.reduce((sum, h) => sum + (h.reps * h.weight), 0);
  const lastWorkout = history.length > 0 ? history[0].workout_date : null;

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--stamp-ember)', marginBottom: 6 }}>
          Training / Exercise
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <h1 style={{ fontSize: 26 }}>{exercise.name}</h1>
          {exercise.is_bfs_core && <Badge tone="ember">BFS core lift</Badge>}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 14 }}>{exercise.category} · {exercise.muscle_group}</div>
        {exercise.description && (
          <div style={{ color: 'var(--paper-dim)', marginTop: 8, fontSize: 13.5 }}>{exercise.description}</div>
        )}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '28px' }}>
        <Link to="/exercise/workout-logger" style={{ background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '11px 22px', borderRadius: 8, fontWeight: 700, fontSize: 14 }}>
          Log workout
        </Link>
        <Link to={`/exercise/progress?exercise=${id}`} style={{ background: 'var(--ink-700)', color: 'var(--paper)', padding: '11px 22px', borderRadius: 8, fontWeight: 600, fontSize: 14 }}>
          View progress
        </Link>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '14px', marginBottom: '28px' }}>
        <Card>
          <div style={statLabel}>Max weight</div>
          <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)', marginTop: 8 }}>{maxWeight} lbs</div>
        </Card>
        <Card>
          <div style={statLabel}>Total sets</div>
          <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)', marginTop: 8 }}>{totalSets}</div>
        </Card>
        <Card>
          <div style={statLabel}>Total volume</div>
          <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)', marginTop: 8 }}>{totalVolume.toLocaleString()} lbs</div>
        </Card>
        <Card>
          <div style={statLabel}>Last workout</div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--paper)', marginTop: 8 }}>{lastWorkout ? new Date(lastWorkout).toLocaleDateString() : 'N/A'}</div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px' }}>
        {/* Personal Records */}
        <Card>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>Personal records</h2>
          {records.length === 0 ? (
            <div style={{ color: 'var(--muted)', textAlign: 'center', padding: '28px 0' }}>No personal records yet</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {records.map((record) => (
                <div key={record.id} style={{ borderLeft: '3px solid var(--stamp-ember)', paddingLeft: 14, paddingTop: 4, paddingBottom: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--paper)' }}>{record.record_type}</div>
                      <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{new Date(record.date_achieved).toLocaleDateString()}</div>
                      {record.notes && <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{record.notes}</div>}
                    </div>
                    <div style={{ fontSize: '20px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)' }}>
                      {record.value} {record.record_type.includes('RM') ? 'lbs' : ''}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Recent History */}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>Recent sets</h2>
            <Link to={`/exercise/progress?exercise=${id}`} style={{ color: 'var(--stamp-ember)', fontSize: 12, fontWeight: 600 }}>View all →</Link>
          </div>
          {history.length === 0 ? (
            <div style={{ color: 'var(--muted)', textAlign: 'center', padding: '28px 0' }}>No workout history yet</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ink-700)' }}>
                    <th style={{ padding: '8px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Date</th>
                    <th style={{ padding: '8px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Set</th>
                    <th style={{ padding: '8px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Reps</th>
                    <th style={{ padding: '8px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>Weight</th>
                    <th style={{ padding: '8px', textAlign: 'left', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>RPE</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 15).map((set, index) => {
                    const tone = rpeTone(set.rpe);
                    return (
                      <tr key={index} style={{ borderBottom: '1px solid var(--ink-700)' }}>
                        <td style={{ padding: '8px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)' }}>
                          {new Date(set.workout_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        </td>
                        <td style={{ padding: '8px', color: 'var(--paper-dim)' }}>{set.set_number}</td>
                        <td style={{ padding: '8px', color: 'var(--paper-dim)' }}>{set.reps}</td>
                        <td style={{ padding: '8px', fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--paper)' }}>{set.weight} lbs</td>
                        <td style={{ padding: '8px' }}>
                          <span style={{ padding: '2px 8px', fontSize: 11, fontWeight: 700, borderRadius: 6, background: tone.bg, color: tone.fg }}>
                            {set.rpe}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
