import axios from 'axios';

const API_BASE_URL = '/api/v1';

export const uploadVideo = async (file: File) => {
  // 1. Ask the API where to put the file
  const presignResponse = await axios.post(`${API_BASE_URL}/upload/presign`, {
    filename: file.name,
    content_type: file.type
  });
  
  
  let { upload_url, job_id, file_identifier } = presignResponse.data;

  if (upload_url.startsWith('http')) {
      const urlObj = new URL(upload_url);
      upload_url = urlObj.pathname.replace('/api/api/', '/api/');
  }

  // 2. PUT the raw file to whatever URL the API provided
  await axios.put(upload_url, file, {
    headers: {
      'Content-Type': file.type,
    }
  });

  // 3. Tell the API the upload is finished
  const startResponse = await axios.post(`${API_BASE_URL}/transcribe/start`, {
    job_id: job_id,
    file_identifier: file_identifier
  });

  return startResponse.data;
};

export const checkStatus = async (jobId: string) => {
  const response = await axios.get(`${API_BASE_URL}/status/${jobId}`);
  return response.data;
};

export const cancelJob = async (jobId: string) => {
  const response = await axios.delete(`${API_BASE_URL}/status/${jobId}`);
  return response.data;
};