// Role-specific feedback question sets — plain data, same spirit as the backend's
// security_questions.py pool. Each question is { key, label, type: 'rating'|'text' }.
// 'general' isn't listed here — it renders FeedbackButton's original, unchanged form.

export const REVIEWER_ROLES = [
  { key: 'engineer', label: 'Software Engineer' },
  { key: 'tax_pro', label: 'Tax or Accounting Professional' },
  { key: 'general', label: "Just trying it out" },
]

export const FEEDBACK_SETS = {
  engineer: {
    intro:
      'Feel free to glance at the code too — github.com/Namya0909/missionledger.',
    questions: [
      { key: 'overall_rating', label: 'Overall, how would you rate this as an engineering project?', type: 'rating' },
      {
        key: 'security_impression',
        label: 'Did anything about how it handles your data, uploads, or login feel genuinely solid — or genuinely weak?',
        type: 'text',
      },
      {
        key: 'ai_separation',
        label:
          "The app's rule is \"Python computes every number, AI only explains it\" — from what you saw (in the UI or the code), does that separation actually hold up, or did anything feel like AI doing work it shouldn't?",
        type: 'text',
      },
      {
        key: 'would_trust',
        label: "Would you trust this with your own household's or a small business's real financial data? Why or why not?",
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
