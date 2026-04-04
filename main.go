// Immich MCP Server — Photo management tools for Claude.
//
// Part of the immich-photo-manager plugin.
// License: MIT
package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"strings"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

var client *ImmichClient

func main() {
	baseURL := os.Getenv("IMMICH_BASE_URL")
	apiKey := os.Getenv("IMMICH_API_KEY")
	if baseURL == "" || apiKey == "" {
		log.Fatal("IMMICH_BASE_URL and IMMICH_API_KEY environment variables are required")
	}

	port := os.Getenv("MCP_PORT")
	if port == "" {
		port = "8626"
	}

	client = NewImmichClient(baseURL, apiKey)

	// Verify connection
	if _, err := client.Ping(); err != nil {
		log.Printf("Warning: Could not connect to Immich at %s: %v", baseURL, err)
	} else {
		log.Printf("Connected to Immich at %s", baseURL)
	}

	s := server.NewMCPServer(
		"immich-photo-manager",
		"1.0.0",
		server.WithToolCapabilities(true),
	)

	registerTools(s)

	addr := fmt.Sprintf("0.0.0.0:%s", port)
	log.Printf("Immich MCP Server starting on %s (tcp4)", addr)

	mcpHandler := server.NewStreamableHTTPServer(s)

	// Force IPv4 listener so Tailscale (100.x.x.x) can reach the server.
	// Default net.Listen("tcp") on macOS may bind IPv6-only.
	ln, err := net.Listen("tcp4", addr)
	if err != nil {
		log.Fatalf("Listen error: %v", err)
	}

	mux := http.NewServeMux()
	mux.Handle("/mcp", mcpHandler)
	// Health check endpoint
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok","service":"immich-mcp-server"}`))
	})

	log.Printf("Listening on %s", ln.Addr())
	if err := http.Serve(ln, mux); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}

func jsonStr(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

// arg extracts a string argument from the request, returns "" if missing.
func argStr(req mcp.CallToolRequest, key string) string {
	args := req.GetArguments()
	if args == nil {
		return ""
	}
	v, _ := args[key].(string)
	return v
}

func argFloat(req mcp.CallToolRequest, key string, fallback float64) float64 {
	args := req.GetArguments()
	if args == nil {
		return fallback
	}
	v, ok := args[key].(float64)
	if !ok {
		return fallback
	}
	return v
}

func argBool(req mcp.CallToolRequest, key string, fallback bool) bool {
	args := req.GetArguments()
	if args == nil {
		return fallback
	}
	v, ok := args[key].(bool)
	if !ok {
		return fallback
	}
	return v
}

func argStrSlice(req mcp.CallToolRequest, key string) []string {
	args := req.GetArguments()
	if args == nil {
		return nil
	}
	raw, ok := args[key].([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(raw))
	for _, v := range raw {
		out = append(out, fmt.Sprintf("%v", v))
	}
	return out
}

func registerTools(s *server.MCPServer) {

	// ── Health & Stats ─────────────────────────────────────

	s.AddTool(mcp.NewTool("ping",
		mcp.WithDescription("Check Immich server connectivity. Returns 'pong' if connected."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := client.Ping()
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	s.AddTool(mcp.NewTool("get_server_version",
		mcp.WithDescription("Get the Immich server version."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := client.GetServerVersion()
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	s.AddTool(mcp.NewTool("get_statistics",
		mcp.WithDescription("Get library statistics: total photos, videos, and storage usage."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := client.GetStatistics()
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	// ── Asset Info ──────────────────────────────────────────

	s.AddTool(mcp.NewTool("get_asset_info",
		mcp.WithDescription("Get full metadata for a specific asset (EXIF, GPS, dates, camera, etc)."),
		mcp.WithString("asset_id", mcp.Required(), mcp.Description("The unique ID of the asset.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		assetID := argStr(req, "asset_id")
		result, err := client.GetAsset(assetID)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	s.AddTool(mcp.NewTool("get_map_markers",
		mcp.WithDescription("Get all GPS map markers from the library. Returns asset IDs with lat/lon. Use for geographic discovery."),
		mcp.WithString("file_created_after", mcp.Description("Optional ISO date filter (e.g. '2023-01-01').")),
		mcp.WithString("file_created_before", mcp.Description("Optional ISO date filter.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		after := argStr(req, "file_created_after")
		before := argStr(req, "file_created_before")
		result, err := client.GetMapMarkers(after, before, nil)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var markers []json.RawMessage
		json.Unmarshal(result, &markers)
		total := len(markers)
		if total > 500 {
			markers = markers[:500]
		}
		out := map[string]any{"total": total, "markers": markers}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	// ── Search ─────────────────────────────────────────────

	s.AddTool(mcp.NewTool("search_metadata",
		mcp.WithDescription("Search photos by EXIF metadata: location (city/state/country), camera (make/model), date range, favorites, type (IMAGE/VIDEO)."),
		mcp.WithString("city", mcp.Description("Filter by city name (e.g. 'Barcelona', 'Cairo').")),
		mcp.WithString("state", mcp.Description("Filter by state/region.")),
		mcp.WithString("country", mcp.Description("Filter by country (e.g. 'Spain', 'Egypt').")),
		mcp.WithString("make", mcp.Description("Camera manufacturer (e.g. 'Apple', 'Canon').")),
		mcp.WithString("model", mcp.Description("Camera model (e.g. 'iPhone 14 Pro').")),
		mcp.WithString("taken_after", mcp.Description("ISO date — only photos after this date.")),
		mcp.WithString("taken_before", mcp.Description("ISO date — only photos before this date.")),
		mcp.WithString("asset_type", mcp.Description("'IMAGE' or 'VIDEO'.")),
		mcp.WithNumber("page", mcp.Description("Page number (default 1).")),
		mcp.WithNumber("size", mcp.Description("Results per page (default 50, max 200).")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		page := int(argFloat(req, "page", 1))
		size := int(argFloat(req, "size", 50))
		if size > 200 {
			size = 200
		}
		searchReq := MetadataSearchRequest{
			City:        argStr(req, "city"),
			State:       argStr(req, "state"),
			Country:     argStr(req, "country"),
			Make:        argStr(req, "make"),
			Model:       argStr(req, "model"),
			TakenAfter:  argStr(req, "taken_after"),
			TakenBefore: argStr(req, "taken_before"),
			Type:        argStr(req, "asset_type"),
			Page:        page,
			Size:        size,
		}
		result, err := client.SearchMetadata(searchReq)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var parsed map[string]any
		json.Unmarshal(result, &parsed)
		assets := map[string]any{}
		if a, ok := parsed["assets"].(map[string]any); ok {
			assets = a
		}
		out := map[string]any{
			"total":  assets["total"],
			"page":   page,
			"assets": assets["items"],
		}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("search_smart",
		mcp.WithDescription("AI-powered visual search using CLIP. Describe what you're looking for in natural language (e.g. 'sunset at the beach', 'birthday cake')."),
		mcp.WithString("query", mcp.Required(), mcp.Description("Natural language description of what to find.")),
		mcp.WithString("city", mcp.Description("Optional city filter.")),
		mcp.WithString("state", mcp.Description("Optional state/region filter.")),
		mcp.WithString("country", mcp.Description("Optional country filter.")),
		mcp.WithString("taken_after", mcp.Description("ISO date — only photos after this date.")),
		mcp.WithString("taken_before", mcp.Description("ISO date — only photos before this date.")),
		mcp.WithNumber("page", mcp.Description("Page number (default 1).")),
		mcp.WithNumber("size", mcp.Description("Results per page (default 50, max 200).")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		page := int(argFloat(req, "page", 1))
		size := int(argFloat(req, "size", 50))
		if size > 200 {
			size = 200
		}
		searchReq := SmartSearchRequest{
			Query:       argStr(req, "query"),
			City:        argStr(req, "city"),
			State:       argStr(req, "state"),
			Country:     argStr(req, "country"),
			TakenAfter:  argStr(req, "taken_after"),
			TakenBefore: argStr(req, "taken_before"),
			Page:        page,
			Size:        size,
		}
		result, err := client.SearchSmart(searchReq)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var parsed map[string]any
		json.Unmarshal(result, &parsed)
		assets := map[string]any{}
		if a, ok := parsed["assets"].(map[string]any); ok {
			assets = a
		}
		out := map[string]any{
			"total":  assets["total"],
			"page":   page,
			"assets": assets["items"],
		}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	// ── Albums ──────────────────────────────────────────────

	s.AddTool(mcp.NewTool("list_albums",
		mcp.WithDescription("List all albums with their asset counts."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := client.ListAlbums(nil)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var albums []map[string]any
		json.Unmarshal(result, &albums)
		simplified := make([]map[string]any, 0, len(albums))
		for _, a := range albums {
			simplified = append(simplified, map[string]any{
				"id":            a["id"],
				"albumName":     a["albumName"],
				"description":   a["description"],
				"assetCount":    a["assetCount"],
				"shared":        a["shared"],
				"hasSharedLink": a["hasSharedLink"],
				"createdAt":     a["createdAt"],
			})
		}
		out := map[string]any{"total": len(simplified), "albums": simplified}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("get_album",
		mcp.WithDescription("Get album details including all asset IDs."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("The album's unique ID.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		result, err := client.GetAlbum(albumID)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var album map[string]any
		json.Unmarshal(result, &album)
		var assetIDs []string
		if assets, ok := album["assets"].([]any); ok {
			for _, a := range assets {
				if m, ok := a.(map[string]any); ok {
					if id, ok := m["id"].(string); ok {
						assetIDs = append(assetIDs, id)
					}
				}
			}
		}
		out := map[string]any{
			"id":            album["id"],
			"albumName":     album["albumName"],
			"description":   album["description"],
			"assetCount":    album["assetCount"],
			"shared":        album["shared"],
			"hasSharedLink": album["hasSharedLink"],
			"createdAt":     album["createdAt"],
			"updatedAt":     album["updatedAt"],
			"asset_ids":     assetIDs,
		}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("create_album",
		mcp.WithDescription("Create a new album."),
		mcp.WithString("name", mcp.Required(), mcp.Description("Album name (e.g. 'Roma, Italia').")),
		mcp.WithString("description", mcp.Description("Optional description.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		name := argStr(req, "name")
		desc := argStr(req, "description")
		result, err := client.CreateAlbum(name, desc, nil)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	s.AddTool(mcp.NewTool("update_album",
		mcp.WithDescription("Update an album's name or description."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("The album's unique ID.")),
		mcp.WithString("name", mcp.Description("New name (empty = don't change).")),
		mcp.WithString("description", mcp.Description("New description (empty = don't change).")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		name := argStr(req, "name")
		desc := argStr(req, "description")
		result, err := client.UpdateAlbum(albumID, name, desc)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(string(result)), nil
	})

	s.AddTool(mcp.NewTool("delete_album",
		mcp.WithDescription("Delete an album. Photos are NOT deleted, only the album container."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("The album's unique ID.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		if err := client.DeleteAlbum(albumID); err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(jsonStr(map[string]any{"deleted": true, "album_id": albumID})), nil
	})

	s.AddTool(mcp.NewTool("add_assets_to_album",
		mcp.WithDescription("Add photos/videos to an album."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("Target album ID.")),
		mcp.WithArray("asset_ids", mcp.Required(), mcp.Description("List of asset IDs to add.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		ids := argStrSlice(req, "asset_ids")
		result, err := client.AddAssetsToAlbum(albumID, ids)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		out := map[string]any{"album_id": albumID, "added": len(ids), "result": json.RawMessage(result)}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("remove_assets_from_album",
		mcp.WithDescription("Remove photos/videos from an album. The photos themselves are NOT deleted."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("Target album ID.")),
		mcp.WithArray("asset_ids", mcp.Required(), mcp.Description("List of asset IDs to remove.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		ids := argStrSlice(req, "asset_ids")
		result, err := client.RemoveAssetsFromAlbum(albumID, ids)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		out := map[string]any{"album_id": albumID, "removed": len(ids), "result": json.RawMessage(result)}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	// ── Shared Links ───────────────────────────────────────

	s.AddTool(mcp.NewTool("list_shared_links",
		mcp.WithDescription("List all shared links (public URLs for albums/assets)."),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		result, err := client.ListSharedLinks()
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var links []map[string]any
		json.Unmarshal(result, &links)
		simplified := make([]map[string]any, 0, len(links))
		for _, l := range links {
			albumID := ""
			albumName := ""
			if album, ok := l["album"].(map[string]any); ok {
				albumID, _ = album["id"].(string)
				albumName, _ = album["albumName"].(string)
			}
			simplified = append(simplified, map[string]any{
				"id":          l["id"],
				"key":         l["key"],
				"type":        l["type"],
				"description": l["description"],
				"album_id":    albumID,
				"album_name":  albumName,
			})
		}
		out := map[string]any{"total": len(simplified), "links": simplified}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("create_shared_link",
		mcp.WithDescription("Create a public shared link for an album. Makes it publicly accessible via Immich's sharing URL."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("The album to share.")),
		mcp.WithBoolean("allow_download", mcp.Description("Allow visitors to download photos (default true).")),
		mcp.WithBoolean("show_metadata", mcp.Description("Show EXIF metadata to visitors (default true).")),
		mcp.WithString("description", mcp.Description("Optional link description.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		allowDL := argBool(req, "allow_download", true)
		showMeta := argBool(req, "show_metadata", true)
		desc := argStr(req, "description")

		result, err := client.CreateSharedLink(albumID, allowDL, showMeta, desc)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var parsed map[string]any
		json.Unmarshal(result, &parsed)
		key, _ := parsed["key"].(string)
		out := map[string]any{
			"id":       parsed["id"],
			"key":      key,
			"album_id": albumID,
			"url":      client.BaseURL + "/share/" + key,
		}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})

	s.AddTool(mcp.NewTool("delete_shared_link",
		mcp.WithDescription("Delete a shared link (unpublish from Gallery)."),
		mcp.WithString("link_id", mcp.Required(), mcp.Description("The shared link ID to delete.")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		linkID := argStr(req, "link_id")
		if err := client.DeleteSharedLink(linkID); err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		return mcp.NewToolResultText(jsonStr(map[string]any{"deleted": true, "link_id": linkID})), nil
	})

	// ── Thumbnails ─────────────────────────────────────────

	s.AddTool(mcp.NewTool("get_asset_thumbnail",
		mcp.WithDescription("Get a base64-encoded thumbnail image for an asset. Returns the image data as a base64 string with its MIME type. Use size='thumbnail' for grid views (~250px) or size='preview' for lightbox (~1440px)."),
		mcp.WithString("asset_id", mcp.Required(), mcp.Description("The unique ID of the asset.")),
		mcp.WithString("size", mcp.Description("'thumbnail' (default, ~250px) or 'preview' (~1440px).")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		assetID := argStr(req, "asset_id")
		sizeStr := argStr(req, "size")
		size := ThumbnailSmall
		if sizeStr == "preview" {
			size = ThumbnailPreview
		}

		data, contentType, err := client.GetAssetThumbnail(assetID, size)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}

		b64 := base64.StdEncoding.EncodeToString(data)

		// Normalize MIME type
		mimeType := contentType
		if i := strings.Index(mimeType, ";"); i >= 0 {
			mimeType = mimeType[:i]
		}
		mimeType = strings.TrimSpace(mimeType)

		return &mcp.CallToolResult{
			Content: []mcp.Content{
				mcp.NewImageContent(b64, mimeType),
			},
		}, nil
	})

	s.AddTool(mcp.NewTool("get_album_thumbnails",
		mcp.WithDescription("Get base64-encoded thumbnails for assets in an album. Returns {asset_id, data, mime_type} objects plus total_assets and immich_url for linking. By default returns ALL photos in the album. Use count/offset to paginate large albums."),
		mcp.WithString("album_id", mcp.Required(), mcp.Description("The album's unique ID.")),
		mcp.WithNumber("count", mcp.Description("Number of thumbnails to fetch. Default 0 means ALL photos in the album.")),
		mcp.WithNumber("offset", mcp.Description("Skip this many assets from the start (default 0).")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		albumID := argStr(req, "album_id")
		count := int(argFloat(req, "count", 0))
		offset := int(argFloat(req, "offset", 0))

		// Get album to extract asset IDs
		result, err := client.GetAlbum(albumID)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		var album map[string]any
		json.Unmarshal(result, &album)

		type assetMeta struct {
			ID   string
			Date string
		}
		var assetList []assetMeta
		if assets, ok := album["assets"].([]any); ok {
			for _, a := range assets {
				if m, ok := a.(map[string]any); ok {
					id, _ := m["id"].(string)
					date, _ := m["fileCreatedAt"].(string)
					if id != "" {
						assetList = append(assetList, assetMeta{ID: id, Date: date})
					}
				}
			}
		}

		// Capture total before slicing
		totalAssets := len(assetList)

		// Apply offset and count
		if offset >= totalAssets {
			return mcp.NewToolResultText(jsonStr(map[string]any{
				"album_id":     albumID,
				"album_name":   album["albumName"],
				"total_assets": totalAssets,
				"immich_url":   client.BaseURL,
				"thumbnails":   []any{},
			})), nil
		}
		assetList = assetList[offset:]
		if count > 0 && count < len(assetList) {
			assetList = assetList[:count]
		}

		// Fetch thumbnails
		type thumbResult struct {
			AssetID  string `json:"asset_id"`
			Date     string `json:"date,omitempty"`
			Data     string `json:"data"`
			MimeType string `json:"mime_type"`
		}
		thumbnails := make([]thumbResult, 0, len(assetList))
		for _, asset := range assetList {
			data, contentType, err := client.GetAssetThumbnail(asset.ID, ThumbnailSmall)
			if err != nil {
				log.Printf("Thumbnail fetch failed for %s: %v", asset.ID, err)
				continue
			}
			mimeType := contentType
			if i := strings.Index(mimeType, ";"); i >= 0 {
				mimeType = mimeType[:i]
			}
			thumbnails = append(thumbnails, thumbResult{
				AssetID:  asset.ID,
				Date:     asset.Date,
				Data:     base64.StdEncoding.EncodeToString(data),
				MimeType: strings.TrimSpace(mimeType),
			})
		}

		out := map[string]any{
			"album_id":     albumID,
			"album_name":   album["albumName"],
			"total_assets": totalAssets,
			"offset":       offset,
			"count":        len(thumbnails),
			"immich_url":   client.BaseURL,
			"thumbnails":   thumbnails,
		}
		return mcp.NewToolResultText(jsonStr(out)), nil
	})
}
