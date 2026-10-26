// Role-specific feedback question sets — plain data, same spirit as the backend's
// security_questions.py pool. Each question is { key, label, type: 'rating'|'text' }.
// A role with no entry in FEEDBACK_SETS (student, other) renders FeedbackButton's
// original simple form instead — same questions, but still tagged with its own
// reviewer_role so responses stay distinguishable in the admin view/CSV.

export const REVIEWER_ROLES = [
  { key: 'student', label: 'Student' },
  { key: 'corporate_professional', label: 'Corporate Professional' },
  { key: 'tax_pro', label: 'Accounting or Tax Professional' },
  { key: 'other', label: 'Others' },
]

export const FEEDBACK_SETS = {
  corporate_professional: {
    intro: 'Use it the way you would any work tool, then answer as if you were deciding whether to recommend it to a colleague.',
    questions: [
      {
        key: 'overall_rating',
        label: 'Overall, how would you rate this as a tool you’d consider using or recommending at work?',
        type: 'rating',
      },
      {
        key: 'trust_impression',
        label: 'Did anything about how it handles your data or login feel genuinely trustworthy — or make you hesitate?',
        type: 'text',
      },
      {
        key: 'would_trust',
        label: "Would you trust this with your own household's or a small business's real financial data? Why or why not?",
        type: 'text',
      },
      {
        key: 'comparison',
        label: 'How does this compare to other budgeting/expense tools you’ve used, at work or personally?',
        type: 'text',
      },
      { key: 'first_fix', label: 'One thing you’d fix or add first?', type: 'text' },
    ],
  },
  tax_pro: {
    intro:
      "Please try the Tax Prep Pack specifically — sign up as a Small Business or Nonprofit, turn it on from the Members tab if it isn't already, and generate a PDF before answering.",
    questions: [
      { key: 'credibility_rating', label: "Overall, how credible was the Tax Prep Pack's output for a real client?", type: 'rating' },
      {
        key: 'disclaimer_appropriate',
        label:
          'Was the "Prepared to help you file. Not tax advice." framing appropriate, or did anything oversell what the tool actually does?',
        type: 'text',
      },
      {
        key: 'factual_errors',
        label: 'Did you notice anything factually wrong or outdated — a rate, threshold, form name, or filing rule?',
        type: 'text',
      },
      {
        key: 'time_saved',
        label: 'Roughly how much time would this save you or a client during tax prep, if any?',
        type: 'text',
      },
      { key: 'next_addition', label: "What's the single most useful thing you'd want added next?", type: 'text' },
    ],
  },
}
