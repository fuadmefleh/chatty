import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AuthGate from './components/AuthGate';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/ui/ToastProvider';
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
import Transcriptions from './pages/Transcriptions';
import Speakers from './pages/Speakers';
import Insights from './pages/Insights';
import Reminders from './pages/Reminders';
import WikiLayout from './pages/WikiLayout';
import MemoryViewer from './pages/MemoryViewer';
import WikiArticle from './pages/WikiArticle';
import WikiHealth from './pages/WikiHealth';
import WikiReorganize from './pages/WikiReorganize';
import Requests from './pages/Requests';
import Suggestions from './pages/Suggestions';
import VideoProduction from './pages/VideoProduction';
import Webcams from './pages/Webcams';
import SystemStatus from './pages/SystemStatus';
import Settings from './pages/Settings';
import CodeBrowser from './pages/CodeBrowser';
import ServerHealth from './pages/ServerHealth';
import TokenUsage from './pages/TokenUsage';

function RoutedApp() {
  const { pathname } = useLocation();
  return (
    <AppShell>
      <ErrorBoundary key={pathname}>
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
          <Route path="/transcriptions" element={<Transcriptions />} />
          <Route path="/speakers" element={<Speakers />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/reminders" element={<Reminders />} />
          <Route path="/memory" element={<WikiLayout />}>
            <Route index element={<MemoryViewer />} />
            <Route path="health" element={<WikiHealth />} />
            <Route path="reorganize" element={<WikiReorganize />} />
            <Route path=":type/:slug" element={<WikiArticle />} />
          </Route>
          <Route path="/requests" element={<Requests />} />
          <Route path="/suggestions" element={<Suggestions />} />
          <Route path="/video-production" element={<VideoProduction />} />
          <Route path="/webcams" element={<Webcams />} />
          <Route path="/system" element={<SystemStatus />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/server-health" element={<ServerHealth />} />
          <Route path="/token-usage" element={<TokenUsage />} />
          <Route path="/code" element={<CodeBrowser />} />
        </Routes>
      </ErrorBoundary>
    </AppShell>
  );
}

function App() {
  return (
    <Router>
      <ToastProvider>
        <AuthGate>
          <RoutedApp />
        </AuthGate>
      </ToastProvider>
    </Router>
  );
}

export default App;
