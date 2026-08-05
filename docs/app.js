(function () {
  const tg = window.Telegram.WebApp;
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#1d7dff");

  const form = document.getElementById("search-form");
  const queryInput = document.getElementById("query");
  const statusEl = document.getElementById("status");
  const resultsEl = document.getElementById("results");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = queryInput.value.trim();
    if (!query) return;

    statusEl.textContent = "🔍 Qidirilmoqda...";
    resultsEl.innerHTML = "";

    try {
      const res = await fetch(
        "https://itunes.apple.com/search?media=music&entity=song&limit=10&country=UZ&term=" +
          encodeURIComponent(query)
      );
      const data = await res.json();

      if (!data.results || data.results.length === 0) {
        statusEl.textContent = "❌ Hech narsa topilmadi. Boshqa nom bilan sinab ko'ring.";
        return;
      }

      statusEl.textContent = `🎶 ${data.results.length} ta natija topildi — birini tanlang:`;

      data.results.forEach((track) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "track";

        const img = document.createElement("img");
        img.src = track.artworkUrl60 || "";
        img.alt = "";

        const info = document.createElement("div");
        info.className = "info";

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = track.trackName || "Nomalum";

        const artist = document.createElement("div");
        artist.className = "artist";
        artist.textContent = track.artistName || "";

        info.appendChild(title);
        info.appendChild(artist);
        item.appendChild(img);
        item.appendChild(info);

        item.addEventListener("click", () => selectTrack(track));
        resultsEl.appendChild(item);
      });
    } catch (err) {
      statusEl.textContent = "❌ Qidiruvda xatolik yuz berdi. Keyinroq urinib ko'ring.";
    }
  });

  function selectTrack(track) {
    const query = `${track.trackName} - ${track.artistName}`.trim();
    tg.sendData(`webapp::${query}`);
    tg.close();
  }
})();