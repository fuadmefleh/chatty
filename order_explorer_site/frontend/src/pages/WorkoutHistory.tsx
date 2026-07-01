import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchWorkouts, deleteWorkout } from '../api';
import type { WorkoutSession } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';

const thStyle: React.CSSProperties = {
  padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11,
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)',
};

export default function WorkoutHistory() {
  const [workouts, setWorkouts] = useState<WorkoutSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(20);

  useEffect(() => {
    loadWorkouts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit]);

  const loadWorkouts = async () => {
    try {
      const data = await fetchWorkouts(limit);
      setWorkouts(data);
    } catch (error) {
      console.error('Error loading workouts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this workout?')) {
      return;
    }

    try {
      await deleteWorkout(id);
      setWorkouts(workouts.filter(w => w.id !== id));
    } catch (error) {
      console.error('Error deleting workout:', error);
      alert('Failed to delete workout');
    }
  };

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  const groupedByMonth = workouts.reduce((acc, workout) => {
    const date = new Date(workout.workout_date);
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    if (!acc[monthKey]) {
      acc[monthKey] = [];
    }
    acc[monthKey].push(workout);
    return acc;
  }, {} as Record<string, WorkoutSession[]>);

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader
        eyebrow="Training / Exercise"
        eyebrowColor="var(--stamp-ember)"
        title="Workout history"
        actions={
          <Link to="/exercise/workout-logger" style={{ background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '9px 18px', borderRadius: 8, fontWeight: 700, fontSize: 13 }}>
            Log new workout
          </Link>
        }
      />

      {/* Filters */}
      <Card style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Show</label>
          <select value={limit} onChange={(e) => setLimit(parseInt(e.target.value))} style={{ padding: '8px 12px', borderRadius: 8, fontSize: 13 }}>
            <option value={10}>Last 10 workouts</option>
            <option value={20}>Last 20 workouts</option>
            <option value={50}>Last 50 workouts</option>
            <option value={100}>Last 100 workouts</option>
          </select>
          <div style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--muted)' }}>Total: {workouts.length} workouts</div>
        </div>
      </Card>

      {workouts.length === 0 ? (
        <Card style={{ padding: 48, textAlign: 'center' }}>
          <p style={{ fontSize: 17, color: 'var(--muted)', marginBottom: 16 }}>No workouts logged yet</p>
          <Link to="/exercise/workout-logger" style={{ display: 'inline-block', background: 'var(--stamp-ember)', color: 'var(--ink-900)', padding: '11px 22px', borderRadius: 8, fontWeight: 700, fontSize: 14 }}>
            Log your first workout
          </Link>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
          {Object.entries(groupedByMonth).map(([monthKey, monthWorkouts]) => {
            const [year, month] = monthKey.split('-');
            const monthName = monthNames[parseInt(month) - 1];

            const totalVolume = monthWorkouts.reduce((sum, w) => sum + (w.total_volume || 0), 0);
            const totalSets = monthWorkouts.reduce((sum, w) => sum + (w.exercise_count || 0), 0);

            return (
              <div key={monthKey}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
                  <h2 style={{ fontSize: 17, color: 'var(--paper)' }}>{monthName} {year}</h2>
                  <div style={{ display: 'flex', gap: 18, fontSize: 13, color: 'var(--muted)' }}>
                    <div><strong style={{ color: 'var(--paper)' }}>{monthWorkouts.length}</strong> workouts</div>
                    <div><strong style={{ color: 'var(--paper)' }}>{totalSets}</strong> exercises</div>
                    <div><strong style={{ color: 'var(--paper)' }}>{totalVolume.toLocaleString()}</strong> lbs volume</div>
                  </div>
                </div>

                <div style={{ border: '1px solid var(--ink-700)', borderRadius: 10, overflow: 'hidden' }}>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--ink-750)' }}>
                          <th style={thStyle}>Date</th>
                          <th style={thStyle}>Type</th>
                          <th style={thStyle}>Duration</th>
                          <th style={thStyle}>Exercises</th>
                          <th style={thStyle}>Volume</th>
                          <th style={thStyle}>Notes</th>
                          <th style={{ ...thStyle, textAlign: 'center' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {monthWorkouts.map((workout, idx) => (
                          <tr key={workout.id} style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)', borderTop: '1px solid var(--ink-700)' }}>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>
                              {new Date(workout.workout_date).toLocaleDateString()}
                            </td>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap' }}>
                              <Badge tone="ember">{workout.workout_type}</Badge>
                            </td>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap', fontSize: 13, color: 'var(--paper-dim)' }}>
                              {workout.duration_minutes > 0 ? `${workout.duration_minutes} min` : '—'}
                            </td>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap', fontSize: 13, color: 'var(--paper-dim)' }}>{workout.exercise_count || 0}</td>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap', fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--paper)' }}>
                              {workout.total_volume ? workout.total_volume.toLocaleString() : 0} lbs
                            </td>
                            <td style={{ padding: '13px 16px', fontSize: 12.5, color: 'var(--muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {workout.notes || '—'}
                            </td>
                            <td style={{ padding: '13px 16px', whiteSpace: 'nowrap', textAlign: 'center', fontSize: 13 }}>
                              <Link to={`/exercise/workout/${workout.id}`} style={{ color: 'var(--stamp-teal)', fontWeight: 600, marginRight: 14 }}>View</Link>
                              <button onClick={() => handleDelete(workout.id)} style={{ background: 'transparent', color: 'var(--danger)', border: 'none', padding: 0, fontWeight: 600, fontSize: 13 }}>
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
