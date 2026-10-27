import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Evaluation from './pages/Evaluation'
import Household from './pages/Household'
import Rules from './pages/Rules'
import Trace from './pages/Trace'

function NotFound() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold">Page not found</h1>
      <Link to="/" className="text-teal-dark underline">
        Back to dashboard
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="households/:id" element={<Household />} />
          <Route path="households/:id/trace" element={<Trace />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="rules" element={<Rules />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
