import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="py-10">
      <h1 className="font-mincho text-race-name font-bold text-ink">
        該当する紙面がありません
      </h1>
      <p className="mt-2 text-body text-ink-weak">
        指定されたページは存在しないか、掲載期間を過ぎています。
      </p>
      <p className="mt-4 text-data">
        <Link to="/" className="link-ai">
          番組表へ戻る
        </Link>
      </p>
    </div>
  );
}
