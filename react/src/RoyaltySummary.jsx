import { useEffect, useState } from "react";
import axios from "axios";

function RoyaltySummary() {
  const [summary, setSummary] = useState([]);

  useEffect(() => {
    axios.get("http://localhost:8000/api/royalty-summary/")
      .then(res => setSummary(res.data))
      .catch(err => console.error(err));
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold mb-4">💰 Royalty Summary</h2>
      <table className="w-full border-collapse text-sm">
        <thead className="bg-gray-100 text-gray-700">
          <tr>
            <th className="p-3 text-left">Artist</th>
            <th className="p-3 text-left">Total Plays</th>
            <th className="p-3 text-left">Total Royalties</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((row, idx) => (
            <tr key={idx} className="border-b">
              <td className="p-3">{row['track__artist__name']}</td>
              <td className="p-3">{row.total_plays}</td>
              <td className="p-3">${row.total_royalty.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default RoyaltySummary;
