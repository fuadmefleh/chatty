import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchExerciseStats, fetchWorkouts } from '../api';
import type { ExerciseStats, WorkoutSession } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };

const quickAction = (bg: string): React.CSSProperties => ({
  background: bg,
  color: 'var(--ink-900)',
  padding: '18px',
  borderRadius: 10,
  textAlign: 'center',
  fontWeight: 700,
  fontSize: 14,
  display: 'block',
});

export default function ExerciseDashboard() {
  const [stats, setStats] = useState<ExerciseStats | null>(null);
  const [recentWorkouts, setRecentWorkouts] = useState<WorkoutSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [statsData, workoutsData] = await Promise.all([
          fetchExerciseStats(),
          fetchWorkouts(5)
        ]);
        setStats(statsData);
        setRecentWorkouts(workoutsData);
      } catch (error) {
        console.error('Error loading exercise dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--stamp-ember)" title="Exercise tracker — BFS method" />

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '14px', marginBottom: '28px' }}>
        <Card>
          <div style={statLabel}>Total workouts</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)', marginTop: 8 }}>{stats?.total_workouts || 0}</div>
        </Card>
        <Card>
          <div style={statLabel}>Total sets</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)', marginTop: 8 }}>{stats?.total_sets || 0}</div>
        </Card>
        <Card>
          <div style={statLabel}>Total volume (lbs)</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)', marginTop: 8 }}>{stats?.total_volume.toLocaleString() || 0}</div>
        </Card>
        <Card>
          <div style={statLabel}>Last 30 days</div>
          <div style={{ fontSize: '26px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)', marginTop: 8 }}>{stats?.workouts_last_30_days || 0}</div>
        </Card>
        <Card>
          <div style={statLabel}>Last workout</div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--paper)', marginTop: 8 }}>{stats?.last_workout_date || 'N/A'}</div>
        </Card>
      </div>

      {/* Quick Actions */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '14px', marginBottom: '28px' }}>
        <Link to="/exercise/workout-logger" style={quickAction('var(--stamp-ember)')}>Log workout</Link>
        <Link to="/exercise/exercises" style={quickAction('var(--stamp-gold)')}>View exercises</Link>
        <Link to="/exercise/history" style={quickAction('var(--stamp-teal)')}>Workout history</Link>
        <Link to="/exercise/progress" style={quickAction('#e8c478')}>Track progress</Link>
      </div>

      {/* Recent Workouts */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--muted)' }}>Recent workouts</h2>
          <Link to="/exercise/history" style={{ color: 'var(--stamp-ember)', fontSize: 13, fontWeight: 600 }}>View all →</Link>
        </div>

        {recentWorkouts.length === 0 ? (
          <div style={{ color: 'var(--muted)', textAlign: 'center', padding: '32px 0' }}>
            No workouts yet. Start by logging your first workout.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {recentWorkouts.map((workout) => (
              <Link
                key={workout.id}
                to={`/exercise/workout/${workout.id}`}
                style={{ display: 'block', border: '1px solid var(--ink-700)', borderRadius: 8, padding: 14, background: 'var(--ink-900)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--paper)', fontSize: 14 }}>{workout.workout_type}</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{workout.workout_date}</div>
                    {workout.notes && (
                      <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>{workout.notes}</div>
                    )}
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>{workout.exercise_count || 0} exercises</div>
                    <div style={{ fontSize: 12, color: 'var(--muted)' }}>{workout.duration_minutes > 0 && `${workout.duration_minutes} min`}</div>
                    {workout.total_volume && (
                      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)', marginTop: 2 }}>
                        {workout.total_volume.toLocaleString()} lbs
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>

      {/* BFS Method Info */}
      <Card style={{ marginTop: '28px', borderLeft: '3px solid var(--stamp-ember)' }}>
        <h2 style={{ fontSize: 16, marginBottom: 12, color: 'var(--paper)' }}>About the BFS method</h2>
        <p style={{ marginBottom: 18, fontSize: 13.5, color: 'var(--paper-dim)', lineHeight: 1.6 }}>
          The Bigger, Faster, Stronger (BFS) program is a comprehensive strength and conditioning system designed
          to help athletes reach their full potential.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px' }}>
          {[
            { title: 'Core lifts', items: ['Squat', 'Bench press', 'Power clean', 'Deadlift'] },
            { title: 'Key principles', items: ['Progressive overload', 'Proper form', 'Consistency', 'Recovery'] },
            { title: 'Training focus', items: ['Strength', 'Speed', 'Flexibility', 'Explosiveness'] },
            { title: 'Set-rep schemes', items: ['3x3 (strength)', '5x5 (power)', '10-8-6 (hypertrophy)', '3x5 (volume)'] },
          ].map((group) => (
            <div key={group.title}>
              <h3 style={{ fontSize: 12, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--stamp-ember)', marginBottom: 8 }}>{group.title}</h3>
              <ul style={{ fontSize: 13, color: 'var(--paper-dim)', lineHeight: 1.9, margin: 0, paddingLeft: 16 }}>
                {group.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
