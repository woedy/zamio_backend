import { useEffect, useState } from "react";
import axios from "axios";

function RecentPlays() {
  const [plays, setPlays] = useState([]);

  useEffect(() => {
    axios.get("http://localhost:8000/api/recent-plays/")
      .then(res => setPlays(res.data))
      .catch(err => console.error(err));
  }, []);

  return (
    <div className="p-6">
      <h2 className="text-2xl font-semibold mb-4">🎧 Recent Plays</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100 text-sm text-gray-700">
              <th className="p-3">Track</th>
              <th className="p-3">Artist</th>
              <th className="p-3">Station</th>
              <th className="p-3">Duration</th>
              <th className="p-3">Royalty</th>
              <th className="p-3">Start</th>
            </tr>
          </thead>
          <tbody>
            {plays.map(play => (
              <tr key={play.id} className="border-b text-sm">
                <td className="p-3">{play.track.title}</td>
                <td className="p-3">{play.track.artist}</td>
                <td className="p-3">{play.station}</td>
                <td className="p-3">{play.duration}</td>
                <td className="p-3">${play.royalty_amount}</td>
                <td className="p-3">{new Date(play.start_time).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default RecentPlays;
