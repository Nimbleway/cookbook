import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export default function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48 bg-slate-700" />
          <Skeleton className="h-4 w-32 bg-slate-700" />
        </div>
        <Skeleton className="h-10 w-28 bg-slate-700" />
      </div>

      {/* Charts row */}
      <Card className="bg-slate-800 border-slate-700">
        <CardHeader>
          <Skeleton className="h-5 w-40 bg-slate-700" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-72 w-full bg-slate-700 rounded-lg" />
        </CardContent>
      </Card>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-slate-800 border-slate-700">
            <CardHeader>
              <Skeleton className="h-5 w-32 bg-slate-700" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-4 w-full bg-slate-700" />
              <Skeleton className="h-4 w-5/6 bg-slate-700" />
              <Skeleton className="h-4 w-4/6 bg-slate-700" />
              <Skeleton className="h-4 w-full bg-slate-700" />
              <Skeleton className="h-4 w-3/4 bg-slate-700" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
