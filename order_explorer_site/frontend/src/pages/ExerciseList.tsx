import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchExercises } from '../api';
import type { Exercise } from '../api';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Spinner from '../components/ui/Spinner';
import Input from '../components/ui/form/Input';
import ResponsiveTable from '../components/ui/ResponsiveTable';
import type { TableColumn } from '../components/ui/ResponsiveTable';

const filterBtnClass = (active: boolean): string =>
  `rounded-lg px-4 py-2 text-sm font-semibold ${active ? 'bg-alert-red text-white' : 'bg-surface-dim text-ink-dim'}`;

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
    return (
      <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
        <Spinner label="Loading exercises…" />
      </div>
    );
  }

  const columns: TableColumn<Exercise>[] = [
    {
      key: 'name',
      header: 'Exercise',
      primary: true,
      render: (exercise) => (
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink">{exercise.name}</span>
          {exercise.is_bfs_core && <Badge tone="ember">BFS core</Badge>}
        </div>
      ),
    },
    { key: 'category', header: 'Category', render: (exercise) => <span className="text-sm text-ink-dim">{exercise.category}</span> },
    { key: 'muscle_group', header: 'Muscle group', render: (exercise) => <span className="text-sm text-ink-dim">{exercise.muscle_group}</span> },
    { key: 'description', header: 'Description', render: (exercise) => <span className="text-sm text-muted">{exercise.description}</span> },
    {
      key: 'actions',
      header: 'Actions',
      className: 'text-center',
      render: (exercise) => (
        <Link to={`/exercise/exercise/${exercise.id}`} className="text-sm font-semibold text-alert-red hover:underline">
          View details
        </Link>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-6 md:px-6">
      <PageHeader eyebrow="Training / Exercise" eyebrowColor="var(--alert-red)" title="Exercise library" />

      {/* BFS Core Exercises Highlight */}
      <Card className="mb-7 border-l-[3px] border-l-alert-red">
        <h2 className="mb-4 text-base font-semibold text-ink">BFS core lifts</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {bfsCore.map((exercise) => (
            <Link
              key={exercise.id}
              to={`/exercise/exercise/${exercise.id}`}
              className="block rounded-lg border border-line bg-surface-dim p-3.5 text-center"
            >
              <div className="text-sm font-bold text-ink">{exercise.name}</div>
              <div className="mt-0.5 text-xs text-muted">{exercise.muscle_group}</div>
            </Link>
          ))}
        </div>
      </Card>

      {/* Filters */}
      <Card className="mb-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            type="text"
            placeholder="Search exercises…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            {categories.map((category) => (
              <button key={category} type="button" onClick={() => setFilter(category)} className={filterBtnClass(filter === category)}>
                {category.charAt(0).toUpperCase() + category.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Exercise List */}
      <ResponsiveTable
        columns={columns}
        rows={filteredExercises}
        rowKey={(exercise) => exercise.id}
        emptyTitle="No exercises found"
        emptyDescription="Try a different search term or filter."
      />

      <div className="mt-4 text-sm text-muted">
        Showing {filteredExercises.length} of {exercises.length} exercises
      </div>
    </div>
  );
}
