import Layout from './components/Layout'
import { useHashRoute } from './lib/router'
import Home from './routes/Home'
import Module from './routes/Module'
import Planner from './routes/Planner'
import Grades from './routes/Grades'
import Files from './routes/Files'
import Sync from './routes/Sync'

export default function App() {
  const h = useHashRoute()
  let page = <Home />
  if (h.startsWith('#/module/'))   page = <Module code={h.split('/')[2]} />
  else if (h === '#/planner')      page = <Planner />
  else if (h === '#/grades')       page = <Grades />
  else if (h === '#/files')        page = <Files />
  else if (h === '#/sync')         page = <Sync />
  return <Layout>{page}</Layout>
}
