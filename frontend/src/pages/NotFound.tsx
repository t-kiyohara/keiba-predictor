import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="hero min-h-[70vh]">
      <div className="hero-content text-center">
        <div className="max-w-lg">
          <div className="text-9xl font-black text-base-300 select-none mb-2">404</div>
          <div className="text-6xl mb-6">🐴</div>
          <h1 className="text-3xl font-bold mb-3">ページが見つかりません</h1>
          <p className="text-base opacity-70 mb-8">
            お探しのページは存在しないか、移動した可能性があります。<br />
            馬が逃げてしまったかもしれません。
          </p>
          <div className="flex gap-3 justify-center flex-wrap">
            <Link to="/" className="btn btn-primary">
              ← ダッシュボードに戻る
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
