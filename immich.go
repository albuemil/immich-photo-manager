package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// ImmichClient wraps the Immich REST API.
type ImmichClient struct {
	BaseURL string
	APIKey  string
	HTTP    *http.Client
}

// NewImmichClient creates a client from env-provided config.
func NewImmichClient(baseURL, apiKey string) *ImmichClient {
	return &ImmichClient{
		BaseURL: baseURL,
		APIKey:  apiKey,
		HTTP:    &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *ImmichClient) request(method, path string, body any, params url.Values) (json.RawMessage, error) {
	u := c.BaseURL + "/api" + path
	if params != nil && len(params) > 0 {
		u += "?" + params.Encode()
	}

	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshal body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, u, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("x-api-key", c.APIKey)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(data))
	}
	if resp.StatusCode == 204 || len(data) == 0 {
		return json.RawMessage(`null`), nil
	}
	return json.RawMessage(data), nil
}

// ── Health ──────────────────────────────────────────────

func (c *ImmichClient) Ping() (json.RawMessage, error) {
	return c.request("GET", "/server/ping", nil, nil)
}

func (c *ImmichClient) GetServerVersion() (json.RawMessage, error) {
	return c.request("GET", "/server/version", nil, nil)
}

func (c *ImmichClient) GetStatistics() (json.RawMessage, error) {
	return c.request("GET", "/server/statistics", nil, nil)
}

// ── Assets ──────────────────────────────────────────────

func (c *ImmichClient) GetAsset(assetID string) (json.RawMessage, error) {
	return c.request("GET", "/assets/"+assetID, nil, nil)
}

func (c *ImmichClient) GetMapMarkers(fileCreatedAfter, fileCreatedBefore string, isFavorite *bool) (json.RawMessage, error) {
	params := url.Values{"isArchived": {"false"}}
	if isFavorite != nil {
		params.Set("isFavorite", fmt.Sprintf("%v", *isFavorite))
	}
	if fileCreatedAfter != "" {
		params.Set("fileCreatedAfter", fileCreatedAfter)
	}
	if fileCreatedBefore != "" {
		params.Set("fileCreatedBefore", fileCreatedBefore)
	}
	return c.request("GET", "/map/markers", nil, params)
}

// ── Search ──────────────────────────────────────────────

type MetadataSearchRequest struct {
	City       string `json:"city,omitempty"`
	State      string `json:"state,omitempty"`
	Country    string `json:"country,omitempty"`
	Make       string `json:"make,omitempty"`
	Model      string `json:"model,omitempty"`
	TakenAfter string `json:"takenAfter,omitempty"`
	TakenBefore string `json:"takenBefore,omitempty"`
	IsFavorite *bool  `json:"isFavorite,omitempty"`
	IsArchived *bool  `json:"isArchived,omitempty"`
	Type       string `json:"type,omitempty"`
	Page       int    `json:"page"`
	Size       int    `json:"size"`
}

func (c *ImmichClient) SearchMetadata(req MetadataSearchRequest) (json.RawMessage, error) {
	return c.request("POST", "/search/metadata", req, nil)
}

type SmartSearchRequest struct {
	Query       string `json:"query"`
	City        string `json:"city,omitempty"`
	State       string `json:"state,omitempty"`
	Country     string `json:"country,omitempty"`
	TakenAfter  string `json:"takenAfter,omitempty"`
	TakenBefore string `json:"takenBefore,omitempty"`
	Page        int    `json:"page"`
	Size        int    `json:"size"`
}

func (c *ImmichClient) SearchSmart(req SmartSearchRequest) (json.RawMessage, error) {
	return c.request("POST", "/search/smart", req, nil)
}

// ── Albums ──────────────────────────────────────────────

func (c *ImmichClient) ListAlbums(shared *bool) (json.RawMessage, error) {
	params := url.Values{}
	if shared != nil {
		params.Set("shared", fmt.Sprintf("%v", *shared))
	}
	return c.request("GET", "/albums", nil, params)
}

func (c *ImmichClient) GetAlbum(albumID string) (json.RawMessage, error) {
	return c.request("GET", "/albums/"+albumID, nil, nil)
}

func (c *ImmichClient) CreateAlbum(name, description string, assetIDs []string) (json.RawMessage, error) {
	body := map[string]any{"albumName": name, "description": description}
	if len(assetIDs) > 0 {
		body["assetIds"] = assetIDs
	}
	return c.request("POST", "/albums", body, nil)
}

func (c *ImmichClient) UpdateAlbum(albumID, name, description string) (json.RawMessage, error) {
	body := map[string]any{}
	if name != "" {
		body["albumName"] = name
	}
	if description != "" {
		body["description"] = description
	}
	return c.request("PATCH", "/albums/"+albumID, body, nil)
}

func (c *ImmichClient) DeleteAlbum(albumID string) error {
	_, err := c.request("DELETE", "/albums/"+albumID, nil, nil)
	return err
}

func (c *ImmichClient) AddAssetsToAlbum(albumID string, assetIDs []string) (json.RawMessage, error) {
	body := map[string]any{"ids": assetIDs}
	return c.request("PUT", "/albums/"+albumID+"/assets", body, nil)
}

func (c *ImmichClient) RemoveAssetsFromAlbum(albumID string, assetIDs []string) (json.RawMessage, error) {
	body := map[string]any{"ids": assetIDs}
	return c.request("DELETE", "/albums/"+albumID+"/assets", body, nil)
}

// ── Shared Links ────────────────────────────────────────

func (c *ImmichClient) ListSharedLinks() (json.RawMessage, error) {
	return c.request("GET", "/shared-links", nil, nil)
}

func (c *ImmichClient) CreateSharedLink(albumID string, allowDownload, showMetadata bool, description string) (json.RawMessage, error) {
	body := map[string]any{
		"type":          "ALBUM",
		"albumId":       albumID,
		"allowDownload": allowDownload,
		"showMetadata":  showMetadata,
		"allowUpload":   false,
	}
	if description != "" {
		body["description"] = description
	}
	return c.request("POST", "/shared-links", body, nil)
}

func (c *ImmichClient) DeleteSharedLink(linkID string) error {
	_, err := c.request("DELETE", "/shared-links/"+linkID, nil, nil)
	return err
}
