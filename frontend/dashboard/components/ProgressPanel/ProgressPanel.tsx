import type { Assessment, Progress } from '../../types/concept'

interface ProgressPanelProps {
  progress: Progress | null
  assessments: Assessment[]
}

export default function ProgressPanel({ progress, assessments }: ProgressPanelProps) {
  if (!progress) {
    return (
      <div className="card">
        <p className="card-label">
          Learning Progress
        </p>
        <p className="text-secondary">No data yet.</p>
      </div>
    )
  }

  // Mastered = concept whose assessment was answered correctly (same rule
  // the backend's get_progress uses for total_concepts). Derived here so
  // the panel can show WHICH concepts — not just how many. Intersecting
  // with progress.concepts mirrors the backend's join: a concept whose
  // row was cleared no longer counts, even if its assessment remains.
  const passedNames = new Set<string>()
  for (const a of assessments) {
    if (a.answered && a.correct) {
      passedNames.add(a.concept_name)
    }
  }
  const masteredConcepts = (progress.concepts ?? [])
    .filter((c) => passedNames.has(c.name))
    .sort((a, b) => a.name.localeCompare(b.name))

  return (
    <div className="card">
      <p className="card-label">
        Learning Progress
      </p>

      <div className="progress-total">
        <span className="progress-number">
          {progress.total_concepts}
        </span>
        <span className="progress-total-label">
          concepts mastered
        </span>
      </div>

      {progress.detected != null && progress.detected > progress.total_concepts && (
        <p className="progress-hint">
          {progress.detected - progress.total_concepts} concept
          {progress.detected - progress.total_concepts === 1 ? '' : 's'} detected but not
          yet mastered — answer the assessment questions to level up.
        </p>
      )}

      {masteredConcepts.length > 0 && (
        <div className="progress-concepts">
          {masteredConcepts.map((concept) => (
            <div key={concept.name} className="progress-concept">
              <span className="progress-concept-name">{concept.name}</span>
              <span className="progress-concept-count">{concept.category}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
