import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchExercises } from '../api';
import type { Exercise } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';

const thStyle: React.CSSProperties = {
  padding: '12px 16px', textAlign: 'left', fontWeight: 600, fontSize: 11,
  fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)',
};

const filterBtn = (active: boolean): React.CSSProperties => ({
  background: active ? 'var(--stamp-ember)' : 'var(--ink-700)',
  color: active ? 'var(--ink-900)' : 'var(--paper-dim)',
  padding: '8px 16px',
  fontSize: 13,
  fontWeight: 600,
});

export default function ExerciseList() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const loadExercises = async () => {
      try {
        const data = await fetchExercises();
        setExercises(data);
      } catch (error) {
        console.error('Error loading exercises:', error);
      } finally {
        setLoading(false);
      }
    };

    loadExercises();
  }, []);

  const filteredExercises = exercises.filter((exercise) => {
    const matchesFilter = filter === 'all' || exercise.category === filter;
    const matchesSearch = exercise.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         exercise.muscle_group?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const categories = ['all', 'core', 'auxiliary', 'speed', 'flexibility'];
  const bfsCore = exercises.filter(e => e.is_bfs_core);

  if (loading) {
    return <div style={{ padding: 24, color: 'var(--muted)' }}>Loading exercises…</div>;
  }

  return (
    <div style={{ padding: '24px 24px 48px' }}>
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--stamp-ember)" title="Exercise library" />

      {/* BFS Core Exercises Highlight */}
      <Card style={{ marginBottom: '28px', borderLeft: '3px solid var(--stamp-ember)' }}>
        <h2 style={{ fontSize: 15, marginBottom: 16, color: 'var(--paper)' }}>BFS core lifts</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
          {bfsCore.map((exercise) => (
            <Link
              key={exercise.id}
              to={`/exercise/exercise/${exercise.id}`}
              style={{ background: 'var(--ink-900)', border: '1px solid var(--ink-700)', padding: '14px', borderRadius: 8, textAlign: 'center', display: 'block' }}
            >
              <div style={{ fontWeight: 700, color: 'var(--paper)', fontSize: 14 }}>{exercise.name}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{exercise.muscle_group}</div>
            </Link>
          ))}
        </div>
      </Card>

      {/* Filters */}
      <Card style={{ marginBottom: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <input
            type="text"
            placeholder="Search exercises…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%', padding: '10px 14px', borderRadius: 8, fontSize: 14 }}
          />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {categories.map((category) => (
              <button key={category} onClick={() => setFilter(category)} style={filterBtn(filter === category)}>
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Exercise List */}
      <div style={{ border: '1px solid var(--ink-700)', borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--ink-750)' }}>
                <th style={thStyle}>Exercise</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Muscle group</th>
                <th style={thStyle}>Description</th>
                <th style={{ ...thStyle, textAlign: 'center' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredExercises.map((exercise, idx) => (
                <tr key={exercise.id} style={{ backgroundColor: idx % 2 === 0 ? 'var(--ink-800)' : 'var(--ink-900)', borderTop: '1px solid var(--ink-700)' }}>
                  <td style={{ padding: '13px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 600, color: 'var(--paper)', fontSize: 13.5 }}>{exercise.name}</span>
                      {exercise.is_bfs_core && <Badge tone="ember">BFS core</Badge>}
                    </div>
                  </td>
                  <td style={{ padding: '13px 16px', fontSize: 13, color: 'var(--paper-dim)' }}>{exercise.category}</td>
                  <td style={{ padding: '13px 16px', fontSize: 13, color: 'var(--paper-dim)' }}>{exercise.muscle_group}</td>
                  <td style={{ padding: '13px 16px', fontSize: 13, color: 'var(--muted)' }}>{exercise.description}</td>
                  <td style={{ padding: '13px 16px', textAlign: 'center' }}>
                    <Link to={`/exercise/exercise/${exercise.id}`} style={{ color: 'var(--stamp-ember)', fontWeight: 600, fontSize: 13 }}>
                      View details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredExercises.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--muted)' }}>
            No exercises found matching your criteria.
          </div>
        )}
      </div>

      <div style={{ marginTop: '16px', fontSize: 13, color: 'var(--muted)' }}>
        Showing {filteredExercises.length} of {exercises.length} exercises
      </div>
    </div>
  );
}
