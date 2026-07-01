import { useState, useEffect } from 'react';
import { fetchExercises, fetchExerciseProgress } from '../api';
import type { Exercise, ProgressData } from '../api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';

const statLabel: React.CSSProperties = { margin: 0, fontSize: '11px', color: 'var(--muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em' };
const fieldLabel: React.CSSProperties = { display: 'block', marginBottom: '8px', fontSize: '12px', fontWeight: 600, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' };
const fieldInput: React.CSSProperties = { width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 14 };
const AXIS = { fontSize: 12, fill: '#8b8f92' };
const TOOLTIP_STYLE = { background: '#1b2026', border: '1px solid #262c33', borderRadius: 8, color: '#e9e6dd' };

const ChartCard: React.FC<React.PropsWithChildren<{ title: string }>> = ({ title, children }) => (
  <Card style={{ marginBottom: '20px' }}>
    <h2 style={{ fontSize: 13, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 16, color: 'var(--muted)' }}>{title}</h2>
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
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading…</div>;
  }

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--stamp-ember)" title="Progress tracker" />

      {/* Exercise Selection */}
      <Card style={{ marginBottom: '28px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div>
            <label style={fieldLabel}>Select exercise</label>
            <select value={selectedExercise || ''} onChange={(e) => setSelectedExercise(parseInt(e.target.value))} style={fieldInput}>
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
            </select>
          </div>

          <div>
            <label style={fieldLabel}>Time period</label>
            <select value={days} onChange={(e) => setDays(parseInt(e.target.value))} style={fieldInput}>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 6 months</option>
              <option value={365}>Last year</option>
            </select>
          </div>
        </div>

        {selectedExerciseData && (
          <div style={{ marginTop: 16, padding: 14, background: 'var(--ink-900)', borderRadius: 8, borderLeft: '3px solid var(--stamp-ember)' }}>
            <div style={{ fontWeight: 700, color: 'var(--paper)', fontSize: 14 }}>{selectedExerciseData.name}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>{selectedExerciseData.category} · {selectedExerciseData.muscle_group}</div>
            {selectedExerciseData.description && (
              <div style={{ fontSize: 12.5, color: 'var(--paper-dim)', marginTop: 4 }}>{selectedExerciseData.description}</div>
            )}
          </div>
        )}
      </Card>

      {!selectedExercise ? (
        <Card style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
          Please select an exercise to view progress
        </Card>
      ) : progressData.length === 0 ? (
        <Card style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
          No workout data available for this exercise in the selected time period
        </Card>
      ) : (
        <>
          {/* Stats Cards */}
          {stats && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '14px', marginBottom: '28px' }}>
              <Card>
                <div style={statLabel}>Max weight</div>
                <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-ember)', marginTop: 8 }}>{stats.maxWeight} lbs</div>
              </Card>
              <Card>
                <div style={statLabel}>Avg weight</div>
                <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-gold)', marginTop: 8 }}>{stats.avgWeight.toFixed(1)} lbs</div>
              </Card>
              <Card>
                <div style={statLabel}>Total volume</div>
                <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--stamp-teal)', marginTop: 8 }}>{stats.totalVolume.toLocaleString()} lbs</div>
              </Card>
              <Card>
                <div style={statLabel}>Max reps</div>
                <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#e8c478', marginTop: 8 }}>{stats.maxReps}</div>
              </Card>
              <Card>
                <div style={statLabel}>Sessions</div>
                <div style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--paper-dim)', marginTop: 8 }}>{stats.sessions}</div>
              </Card>
            </div>
          )}

          {/* Weight Progress Chart */}
          <ChartCard title="Weight progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Weight (lbs)', angle: -90, position: 'insideLeft', fill: '#8b8f92' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              <Line type="monotone" dataKey="max_weight" stroke="#d8603f" strokeWidth={2} name="Max weight" dot={{ r: 4, fill: '#d8603f' }} />
              <Line type="monotone" dataKey="avg_weight" stroke="#c89b3c" strokeWidth={2} name="Avg weight" dot={{ r: 3, fill: '#c89b3c' }} strokeDasharray="5 5" />
            </LineChart>
          </ChartCard>

          {/* Volume Progress Chart */}
          <ChartCard title="Volume progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Volume (lbs)', angle: -90, position: 'insideLeft', fill: '#8b8f92' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              <Line type="monotone" dataKey="total_volume" stroke="#4fa8a0" strokeWidth={2} name="Total volume" dot={{ r: 4, fill: '#4fa8a0' }} />
            </LineChart>
          </ChartCard>

          {/* Reps Progress Chart */}
          <ChartCard title="Reps progress">
            <LineChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262c33" />
              <XAxis dataKey="workout_date" tick={AXIS} angle={-45} textAnchor="end" height={80} />
              <YAxis label={{ value: 'Reps', angle: -90, position: 'insideLeft', fill: '#8b8f92' }} tick={AXIS} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 12, color: '#8b8f92' }} />
              <Line type="monotone" dataKey="max_reps" stroke="#e8c478" strokeWidth={2} name="Max reps" dot={{ r: 4, fill: '#e8c478' }} />
            </LineChart>
          </ChartCard>
        </>
      )}
    </div>
  );
}
