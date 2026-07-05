import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchExercise, fetchExerciseHistory, fetchPersonalRecords } from '../api';
import type { Exercise, WorkoutSet, PersonalRecord } from '../api';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

// The history endpoint joins in the session's workout_date, which the shared WorkoutSet type doesn't declare.
type HistorySet = WorkoutSet & { workout_date: string };

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
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <Spinner label="Loading exercise…" />
      </div>
    );
  }

  if (!exercise) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 md:px-6">
        <EmptyState title="Exercise not found" />
      </div>
    );
  }

  const maxWeight = history.length > 0 ? Math.max(...history.map(h => h.weight)) : 0;
  const totalSets = history.length;
  const totalVolume = history.reduce((sum, h) => sum + (h.reps * h.weight), 0);
  const lastWorkout = history.length > 0 ? history[0].workout_date : null;

  const historyColumns: TableColumn<HistorySet & { _idx: number }>[] = [
    {
      key: 'date',
      header: 'Date',
      primary: true,
      render: (row) => (
        <span className="font-mono text-sm text-ink-dim">
          {new Date(row.workout_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      ),
    },
    { key: 'set', header: 'Set', render: (row) => <span className="text-ink-dim">{row.set_number}</span> },
    { key: 'reps', header: 'Reps', render: (row) => <span className="text-ink-dim">{row.reps}</span> },
    { key: 'weight', header: 'Weight', render: (row) => <span className="font-mono font-semibold text-ink">{row.weight} lbs</span> },
    { key: 'rpe', header: 'RPE', render: (row) => <RpeBadge rpe={row.rpe} /> },
  ];

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 md:px-6">
      <PageHeader
        eyebrow="Training / Exercise"
        eyebrowColor="var(--alert-red)"
        title={exercise.name}
        actions={
          <>
            <Link
              to="/exercise/workout-logger"
              className="rounded-lg bg-alert-red px-5 py-2.5 text-sm font-bold text-white"
            >
              Log workout
            </Link>
            <Link
              to={`/exercise/progress?exercise=${id}`}
              className="rounded-lg border border-line bg-surface-dim px-5 py-2.5 text-sm font-semibold text-ink"
            >
              View progress
            </Link>
          </>
        }
      />

      <div className={`flex flex-wrap items-center gap-2 text-sm text-muted ${exercise.description ? 'mb-2' : 'mb-7'}`}>
        <span>{exercise.category} · {exercise.muscle_group}</span>
        {exercise.is_bfs_core && <Badge tone="ember">BFS core lift</Badge>}
      </div>
      {exercise.description && (
        <p className="mb-7 text-[13.5px] text-ink-dim">{exercise.description}</p>
      )}

      {/* Stats Cards */}
      <div className="mb-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Max weight" value={`${maxWeight} lbs`} tone="red" />
        <StatCard label="Total sets" value={totalSets} tone="amber" />
        <StatCard label="Total volume" value={`${totalVolume.toLocaleString()} lbs`} tone="signal" />
        <StatCard label="Last workout" value={lastWorkout ? new Date(lastWorkout).toLocaleDateString() : 'N/A'} tone="neutral" />
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* Personal Records */}
        <Card>
          <h2 className="mb-4 font-mono text-[13px] uppercase tracking-wider text-muted">Personal records</h2>
          {records.length === 0 ? (
            <EmptyState title="No personal records yet" />
          ) : (
            <div className="flex flex-col gap-2.5">
              {records.map((record) => (
                <div key={record.id} className="border-l-[3px] border-alert-red py-1 pl-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-[15px] font-bold text-ink">{record.record_type}</div>
                      <div className="font-mono text-xs text-muted">{new Date(record.date_achieved).toLocaleDateString()}</div>
                      {record.notes && <div className="mt-1 text-xs text-muted">{record.notes}</div>}
                    </div>
                    <div className="whitespace-nowrap font-mono text-xl font-bold text-alert-red">
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
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-mono text-[13px] uppercase tracking-wider text-muted">Recent sets</h2>
            <Link to={`/exercise/progress?exercise=${id}`} className="text-xs font-semibold text-alert-red">View all →</Link>
          </div>
          {history.length === 0 ? (
            <EmptyState title="No workout history yet" />
          ) : (
            <ResponsiveTable
              columns={historyColumns}
              rows={history.slice(0, 15).map((set, i) => ({ ...set, _idx: i }))}
              rowKey={(row) => row._idx}
            />
          )}
        </Card>
      </div>
    </div>
  );
}
