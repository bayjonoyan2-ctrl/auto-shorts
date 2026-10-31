document.getElementById('short-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const TOKEN = prompt("Please enter your GitHub Personal Access Token (needs 'workflow' permissions):");
    if (!TOKEN) return alert("Token is required to trigger the cloud server.");

    const GITHUB_USERNAME = "bayjonoyan2-ctrl";
    const REPO_NAME = "auto-shorts";
    
    const url = document.getElementById('video_url').value;
    const numShorts = document.getElementById('num_shorts').value;
    
    const btn = document.getElementById('submit-btn');
    const statusDiv = document.getElementById('status');
    const statusText = document.getElementById('status-text');

    btn.disabled = true;
    btn.innerText = "Starting Workflow...";
    statusDiv.classList.remove('hidden');
    statusText.innerText = "Sending request to GitHub Cloud...";

    try {
        const response = await fetch(`https://api.github.com/repos/${GITHUB_USERNAME}/${REPO_NAME}/actions/workflows/main.yml/dispatches`, {
            method: 'POST',
            headers: {
                'Accept': 'application/vnd.github.v3+json',
                'Authorization': `Bearer ${TOKEN}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ref: "main",
                inputs: { video_url: url, num_shorts: numShorts }
            })
        });

        if (response.ok) {
            btn.innerText = "Processing in Cloud...";
            statusText.innerHTML = `GitHub is downloading and auto-generating your Shorts. <br><br><a href="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}/actions" target="_blank" style="color:#58a6ff;">Click here to watch the progress and download.</a>`;
        } else {
            throw new Error("Failed to trigger workflow. Check your token.");
        }
    } catch (error) {
        statusText.innerText = `❌ Error: ${error.message}`;
        btn.disabled = false;
        btn.innerText = "Generate Shorts Automatically";
    }
});