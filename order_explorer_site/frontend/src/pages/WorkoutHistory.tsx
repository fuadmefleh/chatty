import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchWorkouts, deleteWorkout } from '../api';
import type { WorkoutSession } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import Select from '../components/ui/form/Select';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

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
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading…" />
      </div>
    );
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

  const columns: TableColumn<WorkoutSession>[] = [
    {
      key: 'date',
      header: 'Date',
      primary: true,
      render: (w) => <span className="whitespace-nowrap font-mono">{new Date(w.workout_date).toLocaleDateString()}</span>,
    },
    { key: 'type', header: 'Type', render: (w) => <Badge tone="ember">{w.workout_type}</Badge> },
    {
      key: 'duration',
      header: 'Duration',
      render: (w) => <span className="text-ink-dim">{w.duration_minutes > 0 ? `${w.duration_minutes} min` : '—'}</span>,
    },
    { key: 'exercises', header: 'Exercises', render: (w) => <span className="text-ink-dim">{w.exercise_count || 0}</span> },
    {
      key: 'volume',
      header: 'Volume',
      render: (w) => <span className="whitespace-nowrap font-mono font-bold text-ink">{w.total_volume ? w.total_volume.toLocaleString() : 0} lbs</span>,
    },
    {
      key: 'notes',
      header: 'Notes',
      render: (w) => <span className="block max-w-[200px] truncate text-xs text-muted" title={w.notes || undefined}>{w.notes || '—'}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      className: 'text-center',
      render: (w) => (
        <div className="flex items-center justify-center gap-3.5 whitespace-nowrap">
          <Link to={`/exercise/workout/${w.id}`} className="font-semibold text-signal hover:underline">View</Link>
          <button type="button" onClick={() => handleDelete(w.id)} className="bg-transparent p-0 font-semibold text-alert-red">
            Delete
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Training / Exercise"
        eyebrowColor="var(--alert-red)"
        title="Workout history"
        actions={
          <Link to="/exercise/workout-logger" className="rounded-lg bg-alert-red px-[18px] py-2 font-bold text-white">
            Log new workout
          </Link>
        }
      />

      {/* Filters */}
      <Card className="mb-6">
        <div className="flex flex-wrap items-center gap-3.5">
          <label className="font-mono text-xs font-semibold uppercase text-muted">Show</label>
          <Select value={limit} onChange={(e) => setLimit(parseInt(e.target.value))} className="max-w-[220px]">
            <option value={10}>Last 10 workouts</option>
            <option value={20}>Last 20 workouts</option>
            <option value={50}>Last 50 workouts</option>
            <option value={100}>Last 100 workouts</option>
          </Select>
          <div className="ml-auto text-sm text-muted">Total: {workouts.length} workouts</div>
        </div>
      </Card>

      {workouts.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="mb-4 text-lg text-muted">No workouts logged yet</p>
          <Link to="/exercise/workout-logger" className="inline-block rounded-lg bg-alert-red px-[22px] py-2.5 font-bold text-white">
            Log your first workout
          </Link>
        </Card>
      ) : (
        <div className="flex flex-col gap-8">
          {Object.entries(groupedByMonth).map(([monthKey, monthWorkouts]) => {
            const [year, month] = monthKey.split('-');
            const monthName = monthNames[parseInt(month) - 1];

            const totalVolume = monthWorkouts.reduce((sum, w) => sum + (w.total_volume || 0), 0);
            const totalSets = monthWorkouts.reduce((sum, w) => sum + (w.exercise_count || 0), 0);

            return (
              <div key={monthKey}>
                <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-lg text-ink">{monthName} {year}</h2>
                  <div className="flex flex-wrap gap-[18px] text-sm text-muted">
                    <div><strong className="text-ink">{monthWorkouts.length}</strong> workouts</div>
                    <div><strong className="text-ink">{totalSets}</strong> exercises</div>
                    <div><strong className="text-ink">{totalVolume.toLocaleString()}</strong> lbs volume</div>
                  </div>
                </div>

                <ResponsiveTable columns={columns} rows={monthWorkouts} rowKey={(w) => w.id} emptyTitle="No workouts" />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
