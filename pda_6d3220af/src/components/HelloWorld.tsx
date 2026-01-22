import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckCircle2 } from 'lucide-react'

export const HelloWorld = () => {
  const features = [
    'React 19 with TypeScript',
    'Tailwind CSS styling',
    'shadcn/ui components',
    'React Router with HashRouter',
    'TanStack Query',
    'Single-file bundle ready'
  ]

  return (
    <div>
      <Card className="max-w-2xl w-full">
        <CardHeader>
          <CardTitle className="text-4xl font-bold text-center bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Hello World
          </CardTitle>
          <CardDescription className="text-center text-lg">
            Your base app is ready! This template includes:
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {features.map((feature) => (
              <li key={feature} className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                <span className="text-gray-700 dark:text-gray-300">{feature}</span>
              </li>
            ))}
          </ul>
          <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              <strong>Next steps:</strong> Customize this app by adding your components to <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">src/components/</code> and pages to <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">src/pages/</code>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
