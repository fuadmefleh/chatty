import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { fetchWorkoutDetails } from '../api';
import type { WorkoutSession, WorkoutSet } from '../api';
import Card from '../components/ui/Card';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

// Badge doesn't have a "green" tone, so RPE severity (which needs green/amber/red)
// is rendered with the same visual shape as Badge but its own tone classes.
const rpeClasses = (rpe: number): string => {
  if (rpe >= 9) return 'bg-alert-red/15 text-alert-red';
  if (rpe >= 7) return 'bg-alert-amber/15 text-alert-amber';
  return 'bg-alert-green/15 text-alert-green';
};

const RpeBadge: React.FC<{ rpe: number }> = ({ rpe }) => (
  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 font-mono text-[11px] font-semibold ${rpeClasses(rpe)}`}>
    {rpe}
  </span>
);

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
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <Spinner label="Loading workout…" />
      </div>
    );
  }

  if (!workout) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <EmptyState title="Workout not found" />
      </div>
    );
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

  const setColumns: TableColumn<WorkoutSet & { _idx: number }>[] = [
    { key: 'set', header: 'Set', primary: true, render: (row) => <span className="font-bold text-ink">Set {row.set_number}</span> },
    { key: 'reps', header: 'Reps', render: (row) => <span className="text-ink-dim">{row.reps}</span> },
    { key: 'weight', header: 'Weight', render: (row) => <span className="text-ink-dim">{row.weight} lbs</span> },
    {
      key: 'volume',
      header: 'Volume',
      render: (row) => <span className="font-mono font-bold text-ink">{(row.reps * row.weight).toFixed(0)} lbs</span>,
    },
    { key: 'rpe', header: 'RPE', render: (row) => <RpeBadge rpe={row.rpe} /> },
    { key: 'notes', header: 'Notes', render: (row) => <span className="text-xs text-muted">{row.notes || '—'}</span> },
  ];

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Training / Exercise"
        eyebrowColor="var(--alert-red)"
        title="Workout details"
      />
      <p className="mb-7 text-sm text-muted">
        {new Date(workout.workout_date).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
      </p>

      {/* Summary Cards */}
      <div className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Workout type" value={<span className="capitalize">{workout.workout_type}</span>} tone="red" />
        <StatCard label="Duration" value={workout.duration_minutes > 0 ? `${workout.duration_minutes} min` : '—'} tone="amber" />
        <StatCard label="Total volume" value={`${totalVolume.toLocaleString()} lbs`} tone="signal" />
        <StatCard label="Exercises" value={Object.keys(groupedSets).length} tone="neutral" />
      </div>

      {/* Notes */}
      {workout.notes && (
        <Card className="mb-7 border-l-[3px] border-l-signal">
          <div className="mb-1 text-[13px] font-bold text-signal">Workout notes</div>
          <div className="text-[13.5px] text-ink-dim">{workout.notes}</div>
        </Card>
      )}

      {/* Exercises and Sets */}
      <div className="flex flex-col gap-5">
        {Object.entries(groupedSets).map(([exerciseName, sets]) => {
          const exerciseVolume = sets.reduce((sum, set) => sum + (set.reps * set.weight), 0);
          const avgRpe = sets.reduce((sum, set) => sum + set.rpe, 0) / sets.length;
          const totalReps = sets.reduce((sum, s) => sum + s.reps, 0);

          return (
            <Card key={exerciseName} padding={0} className="overflow-hidden">
              <div className="border-b border-line bg-surface-dim p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-[17px] text-ink">{exerciseName}</h2>
                    <div className="mt-0.5 text-xs text-muted">
                      {sets[0].category && `${sets[0].category} · `}{sets[0].muscle_group}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-lg font-bold text-alert-red">{sets.length} sets</div>
                    <div className="text-xs text-muted">{exerciseVolume.toLocaleString()} lbs · RPE {avgRpe.toFixed(1)}</div>
                  </div>
                </div>
              </div>

              <div className="p-4">
                <ResponsiveTable
                  columns={setColumns}
                  rows={sets.map((set, i) => ({ ...set, _idx: i }))}
                  rowKey={(row) => row._idx}
                />
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-sm">
                  <span className="font-bold text-ink">Total: {totalReps} reps</span>
                  <span className="font-mono font-bold text-alert-red">{exerciseVolume.toLocaleString()} lbs</span>
                  <span className="font-bold text-ink">Avg RPE {avgRpe.toFixed(1)}</span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
