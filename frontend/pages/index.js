import React from 'react'

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-gray-50">
      <div className="max-w-md mx-auto text-center">
        <h1 className="text-4xl font-bold text-blue-600 mb-4">Atheon AI</h1>
        <p className="text-xl text-gray-700 mb-8">
          Advanced orchestration platform for AI agents with human-in-the-loop workflows
        </p>
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-2xl font-semibold text-gray-800 mb-4">Welcome to Atheon AI Platform</h2>
          <p className="text-gray-600 mb-4">
            This platform helps you manage AI agents and maintain human oversight
            for critical decisions.
          </p>
          <div className="mt-6">
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              onClick={() => alert('Dashboard will be available soon!')}
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}