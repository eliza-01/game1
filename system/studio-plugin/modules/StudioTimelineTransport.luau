-- HTTP boundary for the Timeline editor. No UI, animation or Studio model access.
local StudioTimelineTransport = {}

function StudioTimelineTransport.new(services)
    local HttpService = services.HttpService
    local AGENT_BASE_URL = services.agentBaseUrl
    local AGENT_TOKEN = services.agentToken
    local BRIDGE_URL = services.bridgeUrl
    local BRIDGE_TOKEN = services.bridgeToken

    local function postTimelineAgent(payload: any): any
        local response = HttpService:RequestAsync({
            Url = AGENT_BASE_URL .. "/api/timelines/editor-event",
            Method = "POST",
            Headers = {
                ["X-Control-Token"] = AGENT_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(payload),
        })
        if not response.Success then
            error(("Asset Manager rejected timeline update (HTTP %d): %s"):format(response.StatusCode, response.Body))
        end
        local ok, decoded = pcall(HttpService.JSONDecode, HttpService, response.Body)
        if ok then
            return decoded
        end
        return nil
    end

    local function postTimelineEditorResult(payload: any)
        local response = HttpService:RequestAsync({
            Url = BRIDGE_URL .. "/timeline-editor-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = BRIDGE_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(payload),
        })
        if not response.Success then
            error("game1 timeline editor bridge rejected response: " .. tostring(response.StatusCode))
        end
    end

    return {
        PostAgent = postTimelineAgent,
        PostResult = postTimelineEditorResult,
    }
end

return table.freeze(StudioTimelineTransport)
