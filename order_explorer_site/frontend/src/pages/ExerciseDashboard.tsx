import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchExerciseStats, fetchWorkouts } from '../api';
import type { ExerciseStats, WorkoutSession } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';

const sectionTitle = 'font-mono text-[13px] uppercase tracking-wider text-muted';

const QUICK_ACTIONS: Array<{ to: string; label: string; className: string }> = [
  { to: '/exercise/workout-logger', label: 'Log workout', className: 'bg-alert-red text-bg' },
  { to: '/exercise/exercises', label: 'View exercises', className: 'bg-alert-amber text-bg' },
  { to: '/exercise/history', label: 'Workout history', className: 'bg-signal text-bg' },
  { to: '/exercise/progress', label: 'Track progress', className: 'bg-alert-amber/50 text-ink' },
];

const BFS_GROUPS = [
  { title: 'Core lifts', items: ['Squat', 'Bench press', 'Power clean', 'Deadlift'] },
  { title: 'Key principles', items: ['Progressive overload', 'Proper form', 'Consistency', 'Recovery'] },
  { title: 'Training focus', items: ['Strength', 'Speed', 'Flexibility', 'Explosiveness'] },
  { title: 'Set-rep schemes', items: ['3x3 (strength)', '5x5 (power)', '10-8-6 (hypertrophy)', '3x5 (volume)'] },
];

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
    return (
      <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
        <Spinner label="Loading exercise dashboard…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-12 pt-6 md:px-6">
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--alert-red)" title="Exercise tracker — BFS method" />

      {/* Stats Cards */}
      <div className="mb-7 grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total workouts" value={stats?.total_workouts || 0} tone="red" />
        <StatCard label="Total sets" value={stats?.total_sets || 0} tone="amber" />
        <StatCard label="Total volume (lbs)" value={stats?.total_volume.toLocaleString() || 0} tone="signal" />
        <StatCard label="Last 30 days" value={stats?.workouts_last_30_days || 0} tone="neutral" />
        <StatCard label="Last workout" value={stats?.last_workout_date || 'N/A'} tone="neutral" />
      </div>

      {/* Quick Actions */}
      <div className="mb-7 grid grid-cols-2 gap-3.5 sm:grid-cols-4">
        {QUICK_ACTIONS.map((action) => (
          <Link
            key={action.to}
            to={action.to}
            className={`block rounded-[10px] p-4.5 text-center text-sm font-bold ${action.className}`}
          >
            {action.label}
          </Link>
        ))}
      </div>

      {/* Recent Workouts */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className={sectionTitle}>Recent workouts</h2>
          <Link to="/exercise/history" className="text-[13px] font-semibold text-alert-red">View all →</Link>
        </div>

        {recentWorkouts.length === 0 ? (
          <EmptyState title="No workouts yet" description="Start by logging your first workout." />
        ) : (
          <div className="flex flex-col gap-2.5">
            {recentWorkouts.map((workout) => (
              <Link
                key={workout.id}
                to={`/exercise/workout/${workout.id}`}
                className="block rounded-lg border border-line bg-bg p-3.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-bold text-ink">{workout.workout_type}</div>
                    <div className="mt-0.5 font-mono text-xs text-muted">{workout.workout_date}</div>
                    {workout.notes && (
                      <div className="mt-1 text-xs text-muted">{workout.notes}</div>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-xs text-muted">{workout.exercise_count || 0} exercises</div>
                    <div className="text-xs text-muted">{workout.duration_minutes > 0 && `${workout.duration_minutes} min`}</div>
                    {workout.total_volume && (
                      <div className="mt-0.5 font-mono text-[13px] font-bold text-alert-red">
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
      <Card className="mt-7 border-l-[3px] border-l-alert-red">
        <h2 className="mb-3 text-base font-semibold text-ink">About the BFS method</h2>
        <p className="mb-4.5 text-[13.5px] leading-relaxed text-ink-dim">
          The Bigger, Faster, Stronger (BFS) program is a comprehensive strength and conditioning system designed
          to help athletes reach their full potential.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {BFS_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="mb-2 font-mono text-xs uppercase tracking-wider text-alert-red">{group.title}</h3>
              <ul className="m-0 list-disc pl-4 text-[13px] leading-loose text-ink-dim">
                {group.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
