import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const uploadVideo = async (file: File) => {
  const presignResponse = await axios.post(`/api/v1/upload/presign`, {
    filename: file.name,
    content_type: file.type
  });

  const { upload_url, job_id, file_identifier } = presignResponse.data;

  // 🔥 KEY LOGIC
  if (upload_url.startsWith("http")) {
    // ✅ S3 MODE → direct upload
    await axios.put(upload_url, file, {
      headers: { "Content-Type": file.type }
    });
  } else {
    // ✅ LOCAL MODE → upload via API
    const formData = new FormData();
    formData.append("file", file);

    await axios.post(`/api/v1/upload/local`, formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  }

  const startResponse = await axios.post(`/api/v1/transcribe/start`, {
    job_id,
    file_identifier,
  });

  return startResponse.data;
};

export const checkStatus = async (jobId: string) => {
  const response = await axios.get(`${API_BASE_URL}/status/${jobId}`);
  return response.data;
};

export const cancelJob = async (jobId: string) => {
  const response = await axios.post(`${API_BASE_URL}/cancel/${jobId}`);
  return response.data;
};