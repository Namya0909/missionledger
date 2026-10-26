// Quick-start pot presets, shown as one-tap chips in CreatePotForm so a new user
// doesn't have to think up pot names/types from a blank form — picking one just
// pre-fills the name and type; everything else (budget, approval, etc.) is still
// theirs to set. "Custom" (no chip clicked) always stays fully available.

export const POT_PRESETS = {
  group: [
    { name: 'Food', type: 'spending' },
    { name: 'Conveyance', type: 'spending' },
    { name: 'Rent', type: 'spending' },
    { name: 'Utilities', type: 'spending' },
    { name: 'Entertainment', type: 'spending' },
    { name: 'Shopping', type: 'spending' },
    { name: 'Health', type: 'spending' },
    { name: 'Education', type: 'spending' },
    { name: 'Savings Goal', type: 'savings_goal' },
    { name: 'Miscellaneous', type: 'spending' },
  ],
  nonprofit: [
    { name: 'Program Supplies', type: 'spending' },
    { name: 'Office Rent', type: 'spending' },
    { name: 'Utilities', type: 'spending' },
    { name: 'Staff Salaries', type: 'spending' },
    { name: 'Fundraising', type: 'spending' },
    { name: 'Outreach', type: 'spending' },
    { name: 'Equipment', type: 'spending' },
    { name: 'Travel', type: 'spending' },
    { name: 'Restricted Grant', type: 'restricted_grant' },
    { name: 'General Fund', type: 'free_use' },
  ],
  business: [
    { name: 'Inventory', type: 'spending' },
    { name: 'Rent', type: 'spending' },
    { name: 'Utilities', type: 'spending' },
    { name: 'Payroll', type: 'spending' },
    { name: 'Marketing', type: 'spending' },
    { name: 'Equipment', type: 'spending' },
    { name: 'Insurance', type: 'spending' },
    { name: 'Professional Services', type: 'spending' },
    { name: 'Sales Tax Savings', type: 'reserve' },
    { name: 'Operating Fund', type: 'free_use' },
  ],
}
