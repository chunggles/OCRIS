import { useState } from 'react'
import { useApp } from '../context/AppContext'
import { OCR_STEPS } from '../data/constants'
import { PageHeader } from '../components/ui/index'
import StepPupilInfo  from './upload/StepPupilInfo'
import StepQuality    from './upload/StepQuality'
import StepProcessing from './upload/StepProcessing'
import StepExtraction from './upload/StepExtraction'
import StepValidation from './upload/StepValidation'
import StepConfirm    from './upload/StepConfirm'
import StepSuccess    from './upload/StepSuccess'
import { pupilName }  from './upload/shared'

const SUCCESS_STEP = OCR_STEPS.length + 1

// Wizard. Step 1 collects one or more forms into a queue; steps 2-6 then run for the form at the
// front of it, and saving moves on to the next. Each step receives the accumulated `data` for the
// current form and passes additions to onNext().
export default function UploadPage() {
  const { nav } = useApp()
  const [step,     setStep]     = useState(1)
  const [queue,    setQueue]    = useState([])  // forms still to save, as { file, form }; queue[0] is the current one
  const [stepData, setStepData] = useState({})  // what steps 2-6 have added for the current form
  const [saved,    setSaved]    = useState([])  // results of the forms saved so far
  const data = { ...queue[0], ...stepData }

  const start    = (added) => { setQueue(added.queue); setStepData({}); setStep(2) }
  const goNext   = (added = {}) => { setStepData(d => ({ ...d, ...added })); setStep(s => Math.min(s + 1, SUCCESS_STEP)) }
  const goBack   = () => setStep(s => Math.max(s - 1, 1))
  const succeed  = (result) => { setSaved(list => [...list, result]); setStep(SUCCESS_STEP) }
  const nextForm = () => { setQueue(q => q.slice(1)); setStepData({}); setStep(2) }
  const leave    = (page) => { setStep(1); setQueue([]); setStepData({}); setSaved([]); nav(page) }

  // On the success screen the current form is already counted in `saved`
  const isSuccess = step === SUCCESS_STEP
  const total     = saved.length + queue.length - (isSuccess ? 1 : 0)
  const position  = isSuccess ? saved.length : saved.length + 1
  const remaining = queue.length - 1

  const steps = {
    1: <StepPupilInfo  initial={{ queue }} onNext={start}/>,
    2: <StepQuality    data={data} onNext={goNext} onBack={goBack}/>,
    3: <StepProcessing data={data} onNext={goNext}/>,
    4: <StepExtraction data={data} onNext={goNext} onBack={goBack}/>,
    5: <StepValidation data={data} onNext={goNext} onBack={goBack}/>,
    6: <StepConfirm    data={data} onSuccess={succeed} onBack={goBack}/>,
    [SUCCESS_STEP]: <StepSuccess data={data} result={saved[saved.length - 1]} position={position} total={total}
      remaining={remaining} onNextForm={nextForm} onNav={leave}/>,
  }

  return (
    <div>
      <PageHeader title="Upload Form 137"/>
      {!isSuccess && (
        <div className="step-tabs">
          {OCR_STEPS.map((label, i) => {
            const n = i + 1
            const done = n < step
            return (
              <div key={label} className={`step-tab${step === n ? ' active' : ''}`}
                onClick={() => done && setStep(n)} style={{ cursor: done ? 'pointer' : 'default' }}>
                {done ? '✓ ' : ''}{n}. {label}
              </div>
            )
          })}
        </div>
      )}
      {step > 1 && !isSuccess && total > 1 && (
        <div className="batch-progress">
          <strong>Form {position} of {total}</strong> — {pupilName(data.form)} — {data.file?.name}
        </div>
      )}
      {steps[step]}
    </div>
  )
}
