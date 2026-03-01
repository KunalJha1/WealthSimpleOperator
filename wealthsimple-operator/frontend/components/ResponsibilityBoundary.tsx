export default function ResponsibilityBoundary() {
  return (
    <div className="space-y-4">
      <div className="card p-4 space-y-3 border-l-4 border-blue-500">
        <div className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
          🤖 AI Responsibilities
        </div>
        <ul className="text-sm text-gray-900 space-y-1 ml-4">
          <li>• <span className="font-medium">Portfolio Monitoring:</span> Detect drift, concentration, and volatility signals</li>
          <li>• <span className="font-medium">Risk Scoring:</span> Compute and rank portfolio risks on 0-10 scales</li>
          <li>• <span className="font-medium">Rebalancing Analysis:</span> Generate allocation deltas with tax-aware trade suggestions</li>
          <li>• <span className="font-medium">Meeting Notes Summarization:</span> Extract action items and decisions from call transcripts</li>
          <li>• <span className="font-medium">Tax Opportunity Scanning:</span> Identify synthetic loss harvesting candidates and replacement ETFs</li>
          <li>• <span className="font-medium">Scenario Simulation:</span> Run defensive playbooks for off-trajectory portfolios</li>
          <li>• <span className="font-medium">Risk Prediction:</span> Forecast 30-day trend direction (rising/falling/stable)</li>
          <li>• <span className="font-medium">Client Contact Prioritization:</span> Identify which clients need outreach based on risk and timeline</li>
          <li>• <span className="font-medium">Reasoning & Explanation:</span> Provide decision trace and confidence scores for all outputs</li>
        </ul>
      </div>

      <div className="card p-4 space-y-3 border-l-4 border-emerald-500">
        <div className="text-xs font-semibold text-emerald-700 uppercase tracking-wide">
          ✋ Human Responsibilities (Non-Delegable)
        </div>
        <ul className="text-sm text-gray-900 space-y-1 ml-4">
          <li>• <span className="font-medium">Investment Decisions:</span> Approve or reject all rebalancing plans and trades</li>
          <li>• <span className="font-medium">Client Communication:</span> Schedule calls, send emails, and provide personalized advice</li>
          <li>• <span className="font-medium">Escalation & Judgment:</span> Decide which alerts warrant immediate action vs. monitoring</li>
          <li>• <span className="font-medium">Context & Goals Interpretation:</span> Apply knowledge of client objectives, constraints, and life events</li>
          <li>• <span className="font-medium">Regulatory & Compliance:</span> Ensure all actions comply with securities regulations and firm policies</li>
          <li>• <span className="font-medium">False Positive Feedback:</span> Mark incorrect alerts to improve future detection</li>
          <li>• <span className="font-medium">Trade Execution:</span> Execute approved plans via portfolio management systems</li>
        </ul>
      </div>

      <div className="card p-4 bg-amber-50 border border-amber-200">
        <p className="text-xs text-amber-900 leading-relaxed">
          <strong>⚠️ Important:</strong> This tool provides analytical support and workflow automation for wealth advisors.
          It is <strong>not</strong> financial advice, investment guidance, or a substitute for human judgment. All
          recommendations must be reviewed and approved by the advisor before client communication or execution.
        </p>
      </div>
    </div>
  );
}

