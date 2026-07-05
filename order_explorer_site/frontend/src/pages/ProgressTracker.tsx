import { useState, useEffect } from 'react';
import { fetchExercises, fetchExerciseProgress } from '../api';
import type { Exercise, ProgressData } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import Spinner from '../components/ui/Spinner';
import FormField from '../components/ui/form/FormField';
import Select from '../components/ui/form/Select';

const sectionTitle = 'mb-4 font-mono text-[13px] uppercase tracking-wider text-muted';
const AXIS = { fontSize: 12, fill: 'var(--muted)' };
const TOOLTIP_STYLE = { background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' };
const LEGEND_STYLE = { fontSize: 12, color: 'var(--muted)' };

// Chart line colors — hex equivalents of the design-system tokens (recharts
// needs literal colors, can't consume Tailwind classes / CSS vars for stroke).
const RED = '#b0402d'; // alert-red
const AMBER = '#a8631f'; // alert-amber
const SIGNAL = '#1e6e64'; // signal

const ChartCard: React.FC<React.PropsWithChildren<{ title: string }>> = ({ title, children }) => (
  <Card className="mb-5">
    <h2 className={sectionTitle}>{title}</h2>
    <ResponsiveContainer width="100%" height={300}>
      {children as React.ReactElement}
    </ResponsiveContainer>
  </Card>
);

export default function ProgressTracker() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<number | null>(null);
  const [progressData, setProgressData] = useState<ProgressData[]>([]);
  const [days, setDays] = useState(90);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadExercises = async () => {
      try {
        const data = await fetchExercises();
        setExercises(data);

        const firstCore = data.find(e => e.is_bfs_core);
        if (firstCore) {
          setSelectedExercise(firstCore.id);
        }
      } catch (error) {
        console.error('Error loading exercises:', error);
      } finally {
        setLoading(false);
      }
    };

    loadExercises();
  }, []);

  useEffect(() => {
    if (selectedExercise) {
      loadProgress();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExercise, days]);

  const loadProgress = async () => {
    if (!selectedExercise) return;

    try {
      const data = await fetchExerciseProgress(selectedExercise, days);
      setProgressData(data);
    } catch (error) {
      console.error('Error loading progress:', error);
    }
  };

  const selectedExerciseData = exercises.find(e => e.id === selectedExercise);

  const stats = progressData.length > 0 ? {
    maxWeight: Math.max(...progressData.map(d => d.max_weight)),
    avgWeight: progressData.reduce((sum, d) => sum + d.avg_weight, 0) / progressData.length,
    totalVolume: progressData.reduce((sum, d) => sum + d.total_volume, 0),
    maxReps: Math.max(...progressData.map(d => d.max_reps)),
    sessions: progressData.length
  } : null;

  if (loading) {
    return (
      <div className="mx-auto flex max-w-[1000px] items-center justify-center px-4 py-16 md:px-6">
        <Spinner label="Loading…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--alert-red)" title="Progress tracker" />

      {/* Exercise Selection */}
      <Card className="mb-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FormField label="Select exercise" htmlFor="progress-exercise">
            <Select id="progress-exercise" value={selectedExercise || ''} onChange={(e) => setSelectedExercise(parseInt(e.target.value))}>
              <option value="">Choose an exercise…</option>
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
            </Select>
          </FormField>

          <FormField label="Time period" htmlFor="progress-days">
            <Select id="progress-days" value={days} onChange={(e) => setDays(parseInt(e.target.value))}>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 6 months</option>
              <option value={365}>Last year</option>
            </Select>
          </FormField>
        </div>

        {selectedExerciseData && (
          <div className="mt-4 rounded-lg bg-surface-dim p-3.5 border-l-[3px] border-alert-red">
            <div className="text-sm font-bold text-ink">{selectedExerciseData.name}</div>
            <div className="mt-0.5 text-sm text-muted">{selectedExerciseData.category} · {selectedExerciseData.muscle_group}</div>
            {selectedExerciseData.description && (
              <div className="mt-1 text-xs text-ink-dim">{selectedExerciseData.description}</div>
            )}
          </div>
        )}
      </Card>

      {!selectedExercise ? (
        <Card className="py-12 text-center text-sm text-muted">
          Please select an exercise to view progress
        </Card>
      ) : progressData.length === 0 ? (
        <Card className="py-12 text-center text-sm text-muted">
          No workout data available for this exercise in the selected time period
        </Card>
      ) : (
        <>
          {/* Stats Cards */}
          {stats && (
            <div className="mb-6 grid grid-cols-2 gap-3.5 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard label="Max weight" value={`${stats.maxWeight} lbs`} tone="red" />
              <StatCard label="Avg weight" value={`${stats.avgWeight.toFixed(1)} lbs`} tone="amber" />
              <StatCard label="Total volume" value={`${stats.totalVolume.toLocaleString()} lbs`} tone="signal" />
              <StatCard label="Max reps" value={stats.maxReps} tone="amber" />
              <StatCard label="Sessions" value={stats.sessions} tone="neutral" />
            </div>
          )}

          {/* Weight Progress Chart */}
          <ChartCard title="Weight progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Weight (lbs)', angle: -90, position: 'insideLeft', fill: 'var(--muted)' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Line type="monotone" dataKey="max_weight" stroke={RED} strokeWidth={2} name="Max weight" dot={{ r: 4, fill: RED }} />
              <Line type="monotone" dataKey="avg_weight" stroke={AMBER} strokeWidth={2} name="Avg weight" dot={{ r: 3, fill: AMBER }} strokeDasharray="5 5" />
            </LineChart>
          </ChartCard>

          {/* Volume Progress Chart */}
          <ChartCard title="Volume progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Volume (lbs)', angle: -90, position: 'insideLeft', fill: 'var(--muted)' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Line type="monotone" dataKey="total_volume" stroke={SIGNAL} strokeWidth={2} name="Total volume" dot={{ r: 4, fill: SIGNAL }} />
            </LineChart>
          </ChartCard>

          {/* Reps Progress Chart */}
          <ChartCard title="Reps progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Reps', angle: -90, position: 'insideLeft', fill: 'var(--muted)' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Line type="monotone" dataKey="max_reps" stroke={AMBER} strokeWidth={2} name="Max reps" dot={{ r: 4, fill: AMBER }} />
            </LineChart>
          </ChartCard>
        </>
      )}
    </div>
  );
}
