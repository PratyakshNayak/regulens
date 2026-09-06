import { useRef, useState } from "react";
import "./App.css";

function App() {
  const fileInputRef = useRef(null);
  const [selectedImage, setSelectedImage] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  function handleImageChange(event) {
    const file = event.target.files?.[0];

    if (file) {
      setSelectedImage({
        file: file,
        name: file.name,
        preview: URL.createObjectURL(file),
      });

      setAnalysisResult(null);
    }
  }

  async function analyzeImage() {
    if (!selectedImage) return;

    const formData = new FormData();
    formData.append("image", selectedImage.file);

    try {
      const response = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      setAnalysisResult(data);
    } catch {
      setAnalysisResult({
        detail: "Could not connect to the ReguLens backend.",
      });
    }
  }

  async function downloadReport() {
    if (!analysisResult?.compliance) return;

    const response = await fetch("http://127.0.0.1:8000/report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        filename: selectedImage.name,
        compliance: analysisResult.compliance,
        declarations: analysisResult.declarations,
        rule_checks: analysisResult.rule_checks,
      }),
    });

    const reportBlob = await response.blob();
    const reportUrl = URL.createObjectURL(reportBlob);

    const downloadLink = document.createElement("a");
    downloadLink.href = reportUrl;
    downloadLink.download = "regulens-compliance-report.pdf";
    downloadLink.click();

    URL.revokeObjectURL(reportUrl);
  }

  return (
    <main className="app">
      <section className="hero">
        <p className="eyebrow">REGULENS</p>
        <h1>Check product labels with confidence.</h1>

        <p className="description">
          Upload a package label to identify required declarations and flag
          possible compliance issues.
        </p>

        <input
          ref={fileInputRef}
          className="file-input"
          type="file"
          accept="image/png, image/jpeg, image/jpg"
          onChange={handleImageChange}
        />

        <button
          className="primary-button"
          type="button"
          onClick={() => fileInputRef.current?.click()}
        >
          Choose a product-label image
        </button>

        {selectedImage ? (
          <div className="image-preview">
            <p>
              Selected: <strong>{selectedImage.name}</strong>
            </p>

            <img src={selectedImage.preview} alt="Selected product label" />

            <button
              className="primary-button analyze-button"
              type="button"
              onClick={analyzeImage}
            >
              Analyze label
            </button>

            {analysisResult && (
              <div className="result-box">
                <p className="result-message">
                  {analysisResult.message || analysisResult.detail}
                </p>

                {analysisResult.compliance && (
                  <section
                    className={`compliance-card ${analysisResult.compliance.status
                      .toLowerCase()
                      .replace(" ", "-")}`}
                  >
                    <p className="compliance-label">COMPLIANCE STATUS</p>
                    <h2>{analysisResult.compliance.status}</h2>
                    <p>
                      Compliance score:{" "}
                      <strong>{analysisResult.compliance.score}/100</strong>
                    </p>
                    <p>{analysisResult.compliance.message}</p>

                    {analysisResult.compliance.issues.length > 0 && (
                      <p>
                        Missing: {analysisResult.compliance.issues.join(", ")}
                      </p>
                    )}

                    <button
                      className="report-button"
                      type="button"
                      onClick={downloadReport}
                    >
                      Download compliance report
                    </button>
                  </section>
                )}

                {analysisResult.declarations && (
                  <>
                    <h3>Extracted declarations</h3>

                    <div className="field-grid">
                      {Object.entries(analysisResult.declarations).map(
                        ([fieldName, value]) => (
                          <article className="field-card" key={fieldName}>
                            <p>{fieldName}</p>
                            <strong>{value || "Not detected"}</strong>
                          </article>
                        )
                      )}
                    </div>
                  </>
                )}

                {analysisResult.extracted_text && (
                  <>
                    <h3>Detected text</h3>
                    <pre>{analysisResult.extracted_text}</pre>
                  </>
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="note">Choose a clear JPG or PNG image of a product label.</p>
        )}
      </section>

      <section className="steps" aria-label="How ReguLens works">
        <article>
          <span>01</span>
          <h2>Upload</h2>
          <p>Provide a clear image of the product package or label.</p>
        </article>

        <article>
          <span>02</span>
          <h2>Analyze</h2>
          <p>ReguLens reads declarations and checks compliance rules.</p>
        </article>

        <article>
          <span>03</span>
          <h2>Review</h2>
          <p>See a clear status, missing details, and supporting evidence.</p>
        </article>
      </section>
    </main>
  );
}

export default App;