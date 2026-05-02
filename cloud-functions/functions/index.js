const {onObjectFinalized} = require("firebase-functions/v2/storage");
const admin = require("firebase-admin");
const vision = require("@google-cloud/vision");

admin.initializeApp();

const client = new vision.ImageAnnotatorClient();

exports.analyzeUploadedFrame = onObjectFinalized(
    {region: "us-east1"},
    async (event) => {
      const object = event.data;
      try {
        const bucketName = object.bucket;
        const filePath = object.name || "";
        const contentType = object.contentType || "";

        if (!filePath.startsWith("frames/")) {
          console.log("Skipping non-frame file:", filePath);
          return null;
        }

        if (!contentType.startsWith("image/")) {
          console.log("Skipping non-image file:", filePath, contentType);
          return null;
        }

        // Expected path: frames/{deviceId}/{frameId}.jpg
        const parts = filePath.split("/");
        if (parts.length < 3) {
          console.log("Unexpected path structure:", filePath);
          return null;
        }

        const deviceId = parts[1];
        const fileName = parts[2];
        const frameId = fileName.replace(/\.[^/.]+$/, "");
        const metadata = object.metadata || {};
        const triggerReason = metadata.triggerReason || "unknown";
        const localNames = (metadata.localNames || "")
            .split(",")
            .map((name) => name.trim())
            .filter(Boolean);
        const localDecision = metadata.localDecision || "unknown";

        const gcsUri = `gs://${bucketName}/${filePath}`;

        const [result] = await client.annotateImage({
          image: {source: {imageUri: gcsUri}},
          features: [
            {type: "LABEL_DETECTION", maxResults: 10},
            {type: "FACE_DETECTION", maxResults: 10},
            {type: "OBJECT_LOCALIZATION", maxResults: 10},
          ],
        });

        const labels = (result.labelAnnotations || []).map((l) => ({
          description: l.description || "",
          score: Number(l.score || 0),
        }));

        const objects = (result.localizedObjectAnnotations || []).map((o) => ({
          name: o.name || "",
          score: Number(o.score || 0),
        }));

        const faces = (result.faceAnnotations || []).map((f) => ({
          detectionConfidence: Number(f.detectionConfidence || 0),
          joyLikelihood: f.joyLikelihood || "UNKNOWN",
          sorrowLikelihood: f.sorrowLikelihood || "UNKNOWN",
          angerLikelihood: f.angerLikelihood || "UNKNOWN",
          surpriseLikelihood: f.surpriseLikelihood || "UNKNOWN",
        }));

        const personFromLabels = labels.some((l) => {
          const d = l.description.toLowerCase();
          return d.includes("person") || d.includes("human");
        });

        const personFromObjects = objects.some((o) => {
          const n = o.name.toLowerCase();
          return n.includes("person") || n.includes("human");
        });

        const personDetected =
          personFromLabels || personFromObjects || faces.length > 0;
        const alertRecommended = localDecision === "unknown" || personDetected;

        const payload = {
          deviceId: deviceId,
          frameId: frameId,
          filePath: filePath,
          gcsUri: gcsUri,
          triggerReason: triggerReason,
          localDecision: localDecision,
          localNames: localNames,
          labels: labels,
          objects: objects,
          faces: faces,
          personDetected: personDetected,
          alertRecommended: alertRecommended,
          createdAt: admin.database.ServerValue.TIMESTAMP,
        };

        await admin.database()
            .ref(`recognitions/${deviceId}/${frameId}`)
            .set(payload);

        console.log(
            "Recognition stored:",
            `recognitions/${deviceId}/${frameId}`,
        );
        return null;
      } catch (err) {
        console.error("analyzeUploadedFrame failed:", err);
        return null;
      }
    },
);
