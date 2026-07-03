import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import AuthGate from './components/AuthGate';
import Dashboard from './pages/Dashboard';
import Orders from './pages/Orders';
import Items from './pages/Items';
import ItemDetail from './pages/ItemDetail';
import Months from './pages/Months';
import Years from './pages/Years';
import Categories from './pages/Categories';
import Vendors from './pages/Vendors';
import Search from './pages/Search';
import Budget from './pages/Budget';
import Recurring from './pages/Recurring';
import Export from './pages/Export';
import ExerciseDashboard from './pages/ExerciseDashboard';
import ExerciseList from './pages/ExerciseList';
import ExerciseDetail from './pages/ExerciseDetail';
import WorkoutLogger from './pages/WorkoutLogger';
import WorkoutHistory from './pages/WorkoutHistory';
import WorkoutDetail from './pages/WorkoutDetail';
import ProgressTracker from './pages/ProgressTracker';
import Chat from './pages/Chat';
import Notes from './pages/Notes';
import Insights from './pages/Insights';
import Reminders from './pages/Reminders';
import MemoryViewer from './pages/MemoryViewer';
import Requests from './pages/Requests';
import SystemStatus from './pages/SystemStatus';

function App() {
  return (
    <Router>
      <AuthGate>
        <div className="app-shell">
          <Sidebar />
          <main className="ledger-main">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/orders" element={<Orders />} />
              <Route path="/items" element={<Items />} />
              <Route path="/items/:name" element={<ItemDetail />} />
              <Route path="/months" element={<Months />} />
              <Route path="/years" element={<Years />} />
              <Route path="/categories" element={<Categories />} />
              <Route path="/vendors" element={<Vendors />} />
              <Route path="/search" element={<Search />} />
              <Route path="/budget" element={<Budget />} />
              <Route path="/recurring" element={<Recurring />} />
              <Route path="/export" element={<Export />} />

              {/* Exercise Tracker Routes */}
              <Route path="/exercise" element={<ExerciseDashboard />} />
              <Route path="/exercise/exercises" element={<ExerciseList />} />
              <Route path="/exercise/exercise/:id" element={<ExerciseDetail />} />
              <Route path="/exercise/workout-logger" element={<WorkoutLogger />} />
              <Route path="/exercise/history" element={<WorkoutHistory />} />
              <Route path="/exercise/workout/:id" element={<WorkoutDetail />} />
              <Route path="/exercise/progress" element={<ProgressTracker />} />

              {/* Chatty Routes */}
              <Route path="/chat" element={<Chat />} />
              <Route path="/notes" element={<Notes />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/reminders" element={<Reminders />} />
              <Route path="/memory" element={<MemoryViewer />} />
              <Route path="/requests" element={<Requests />} />
              <Route path="/system" element={<SystemStatus />} />
            </Routes>
          </main>
        </div>
      </AuthGate>
    </Router>
  );
}

export default App;
