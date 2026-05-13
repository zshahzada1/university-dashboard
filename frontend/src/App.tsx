import Layout from './components/Layout'
import { useHashRoute } from './lib/router'
import Home from './routes/Home'
import Module from './routes/Module'
import Planner from './routes/Planner'
import Deadlines from './routes/Deadlines'
import Resources from './routes/Resources'

export default function App() {
  const h = useHashRoute()
  let page = <Home />
  if (h.startsWith('#/module/'))   page = <Module code={h.split('/')[2]} />
  else if (h === '#/planner')      page = <Planner />
  else if (h === '#/deadlines')    page = <Deadlines />
  else if (h === '#/resources')    page = <Resources />
  return <Layout>{page}</Layout>
}