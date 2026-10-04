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

const SUCCESS_STEP = OCR_STEPS.length + 1

// Wizard: each step receives the accumulated `data` and passes additions to onNext()
export default function UploadPage() {
  const { nav } = useApp()
  const [step,   setStep]   = useState(1)
  const [data,   setData]   = useState({})
  const [result, setResult] = useState(null)

  const goNext  = (added = {}) => { setData(d => ({ ...d, ...added })); setStep(s => Math.min(s + 1, SUCCESS_STEP)) }
  const goBack  = () => setStep(s => Math.max(s - 1, 1))
  const succeed = (saved) => { setResult(saved); setStep(SUCCESS_STEP) }
  const leave   = (page) => { setStep(1); setData({}); nav(page) }

  const steps = {
    1: <StepPupilInfo  initial={data} onNext={goNext}/>,
    2: <StepQuality    data={data} onNext={goNext} onBack={goBack}/>,
    3: <StepProcessing data={data} onNext={goNext}/>,
    4: <StepExtraction data={data} onNext={goNext} onBack={goBack}/>,
    5: <StepValidation data={data} onNext={goNext} onBack={goBack}/>,
    6: <StepConfirm    data={data} onSuccess={succeed} onBack={goBack}/>,
    [SUCCESS_STEP]: <StepSuccess data={data} result={result} onNav={leave}/>,
  }

  return (
    <div>
      <PageHeader title="Upload Form 137"/>
      {step < SUCCESS_STEP && (
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
      {steps[step]}
    </div>
  )
}
