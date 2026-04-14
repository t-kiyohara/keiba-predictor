import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-[70vh]">
      <div className="text-center max-w-lg p-8">
        <div className="text-9xl font-black text-stone-03 select-none mb-2">404</div>
        <div className="text-6xl mb-6">🐴</div>
        <h1 className="text-2xl font-bold mb-3 text-text-black">ページが見つかりません</h1>
        <p className="text-base text-text-grey mb-8">
          お探しのページは存在しないか、移動した可能性があります。<br />
          馬が逃げてしまったかもしれません。
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link to="/" className="btn-primary">
            ← ダッシュボードに戻る
          </Link>
        </div>
      </div>
    </div>
  );
}
