import { useState, useEffect } from 'react'

import UploadScreen from './screens/UploadScreen'

import ProgressScreen from './screens/ProgressScreen'

import DashboardScreen from './screens/DashboardScreen'

import DrilldownScreen from './screens/DrilldownScreen'

import { api } from './api/client'



const TASK_KEY = 'zeroproblems_task_id'

const DEMO_KEY = 'zeroproblems_demo'

const THEME_KEY = 'omsk_pulse_theme'



export default function App() {

  const [screen, setScreen] = useState('upload')

  const [taskId, setTaskId] = useState(() => localStorage.getItem(TASK_KEY) || null)

  const [isDemo, setIsDemo] = useState(() => localStorage.getItem(DEMO_KEY) === '1')

  const [selectedDistrict, setSelectedDistrict] = useState(null)

  const [dark, setDark] = useState(false)

  const [bootstrapped, setBootstrapped] = useState(false)



  useEffect(() => {

    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')

    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light')

  }, [dark])



  useEffect(() => {

    const saved = localStorage.getItem(THEME_KEY)

    if (saved === 'dark') setDark(true)

  }, [])



  useEffect(() => {

    if (bootstrapped) return



    const demo = localStorage.getItem(DEMO_KEY) === '1'

    const tid = localStorage.getItem(TASK_KEY)



    if (demo) {

      setIsDemo(true)

      setScreen('dashboard')

      setBootstrapped(true)

      return

    }



    if (!tid) {

      setBootstrapped(true)

      return

    }



    setTaskId(tid)

    api.getJob(tid)

      .then((job) => {

        if (job.status === 'completed') setScreen('dashboard')

        else if (job.status === 'failed') setScreen('progress')

        else setScreen('progress')

      })

      .catch(() => setScreen('upload'))

      .finally(() => setBootstrapped(true))

  }, [bootstrapped])



  const handleUploadStarted = (id) => {

    setIsDemo(false)

    localStorage.removeItem(DEMO_KEY)

    localStorage.setItem(TASK_KEY, id)

    setTaskId(id)

    setScreen('progress')

  }



  const handleDemoStart = () => {

    setIsDemo(true)

    localStorage.setItem(DEMO_KEY, '1')

    localStorage.removeItem(TASK_KEY)

    setTaskId(null)

    setScreen('progress')

  }



  const handleAnalysisDone = () => setScreen('dashboard')



  const handleDistrictClick = (d) => {

    setSelectedDistrict(d)

    setScreen('drilldown')

  }



  const handleBack = () => {

    setSelectedDistrict(null)

    setScreen('dashboard')

  }



  const handleReset = () => {

    localStorage.removeItem(TASK_KEY)

    localStorage.removeItem(DEMO_KEY)

    setTaskId(null)

    setIsDemo(false)

    setSelectedDistrict(null)

    setScreen('upload')

  }



  const toggleTheme = () => setDark((d) => !d)



  if (!bootstrapped) {

    return (

      <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }} />

    )

  }



  return (

    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>

      {screen === 'upload' && (

        <UploadScreen

          onUploadStarted={handleUploadStarted}

          onDemoStart={handleDemoStart}

          dark={dark}

          onToggleTheme={toggleTheme}

        />

      )}

      {screen === 'progress' && (

        <ProgressScreen
          taskId={isDemo ? null : taskId}
          onDone={handleAnalysisDone}
          onReset={handleReset}
        />

      )}

      {screen === 'dashboard' && (

        <DashboardScreen

          taskId={isDemo ? null : taskId}

          isDemo={isDemo}

          onDistrictClick={handleDistrictClick}

          onReset={handleReset}

          dark={dark}

          onToggleTheme={toggleTheme}

        />

      )}

      {screen === 'drilldown' && selectedDistrict && (

        <DrilldownScreen

          district={selectedDistrict}

          taskId={isDemo ? null : taskId}

          onBack={handleBack}

          dark={dark}

          onToggleTheme={toggleTheme}

        />

      )}

    </div>

  )

}


