-- Edit-mode authoring. Selection belongs to this dock, never to Explorer.
local Workspace=game:GetService("Workspace")
local RunService=game:GetService("RunService")
local History=game:GetService("ChangeHistoryService")
local Http=game:GetService("HttpService")
local Routes={}
local ROOT="Game1RescueRoutes"
local DEFAULT_CATALOG="Unsorted"
local function root(create)
    local f=Workspace:FindFirstChild(ROOT)
    if not f and create then f=Instance.new("Folder"); f.Name=ROOT; f.Parent=Workspace end
    assert(not f or f:IsA("Folder"),"Rescue route root must be a Folder")
    return f
end
local function isRoute(route,f)
    return f~=nil and route~=nil and route.Parent==f and route:IsA("Folder")
        and #route.Name==42 and route.Name:match("^Route_[%x%-]+$")~=nil
end
local function read(route)
    local values={}
    for _,v in ipairs(route:GetChildren()) do if v:IsA("Vector3Value") and tonumber(v.Name) then table.insert(values,v) end end
    table.sort(values,function(a,b) return tonumber(a.Name)<tonumber(b.Name) end)
    local result={}; for _,v in ipairs(values) do table.insert(result,v.Value) end; return result
end
-- Snap a clicked ground position to an existing route in real 3D.
-- Keep the old one-stud snap radius, but never snap to another floor.
local function snapPoint(hit, saved, edited)
    local best,p,owner=1,hit,nil
    local function consider(q,route)
        local d=(q-hit).Magnitude
        if d<best and math.abs(q.Y-hit.Y)<=.25 then best=d; p=q; owner=route end
    end
    for _,route in ipairs(saved) do
        if route~=edited then
            local points=read(route)
            for i,v in ipairs(points) do
                consider(v,route)
                if i>1 then
                    local a=points[i-1]; local delta=v-a; local lengthSquared=delta:Dot(delta)
                    if lengthSquared>1e-8 then
                        local t=math.clamp((hit-a):Dot(delta)/lengthSquared,0,1)
                        consider(a+delta*t,route)
                    end
                end
            end
        end
    end
    return p,owner
end
local function metadata(route)
    local name=route:GetAttribute("RouteDisplayName")
    local catalog=route:GetAttribute("RouteCatalog")
    return if type(name)=="string" and name~="" then name else "Route "..route.Name:sub(7,14),
        if type(catalog)=="string" and catalog~="" then catalog else DEFAULT_CATALOG
end
local function records(f)
    local result={}
    if f then for _,route in ipairs(f:GetChildren()) do if isRoute(route,f) then table.insert(result,route) end end end
    table.sort(result,function(a,b)
        local an,ac=metadata(a); local bn,bc=metadata(b)
        if ac~=bc then return ac<bc end
        if an~=bn then return an<bn end
        return a.Name<b.Name
    end)
    return result
end
local function cleanText(value,default)
    local text=value:match("^%s*(.-)%s*$")
    if text=="" then text=default end
    assert(utf8.len(text) and utf8.len(text)<=80 and not text:find("%c"),"Name/catalog: maximum 80 characters, no control characters")
    return text
end
function Routes.new(plugin,toolbar)
    local button=toolbar:CreateButton("Game1RescueRoutes","Draw monster rescue routes","","Rescue Routes")
    local dock=plugin:CreateDockWidgetPluginGui("Game1RescueRoutes_v1",DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right,false,false,320,540,260,320))
    dock.Title="game1 · Rescue Routes"
    local frame=Instance.new("ScrollingFrame"); frame.Size=UDim2.fromScale(1,1); frame.BackgroundColor3=Color3.fromRGB(26,31,39); frame.CanvasSize=UDim2.new(); frame.AutomaticCanvasSize=Enum.AutomaticSize.Y; frame.ScrollBarThickness=5; frame.Parent=dock
    local layout=Instance.new("UIListLayout"); layout.SortOrder=Enum.SortOrder.LayoutOrder; layout.Padding=UDim.new(0,5); layout.Parent=frame
    local order=0
    local function place(gui,parent)
        order+=1; gui.LayoutOrder=order; gui.Parent=parent or frame; return gui
    end
    local function label(text,height,parent)
        local l=Instance.new("TextLabel"); l.Size=UDim2.new(1,-6,0,height or 24); l.Text=text; l.TextWrapped=true; l.TextColor3=Color3.fromRGB(195,218,230); l.BackgroundTransparency=1; l.TextXAlignment=Enum.TextXAlignment.Left; l.Font=Enum.Font.Gotham; l.TextSize=12
        return place(l,parent)
    end
    local status=label("Select a saved route or create a new one.",48)
    local selectedRoute=nil; local draft=nil; local drawing=false; local preview=nil; local busy=false
    local pendingDelete=nil; local deleted=nil; local collapsed={}
    local mouse=plugin:GetMouse()
    local refreshControls,refreshList,refreshPreview
    local function invoke(action)
        if RunService:IsRunning() then status.Text="Stop Play before editing routes"; return end
        if busy then return end
        busy=true
        local ok,err=pcall(action); busy=false
        if refreshControls then refreshControls() end
        if not ok then status.Text=tostring(err) end
    end
    local function line(text,action,parent)
        local b=Instance.new("TextButton"); b.Size=UDim2.new(1,-6,0,30); b.Text=text; b.TextColor3=Color3.new(1,1,1); b.BackgroundColor3=Color3.fromRGB(44,56,68); b.Font=Enum.Font.Gotham; b.TextSize=12; b.TextWrapped=true
        place(b,parent)
        b.Activated:Connect(function() if b.Active then invoke(action) end end)
        return b
    end
    local function enabled(b,yes)
        b.Active=yes; b.AutoButtonColor=yes; b.TextTransparency=if yes then 0 else .55; b.BackgroundTransparency=if yes then 0 else .5
    end
    local function ensureMapId(f)
        local mapId=f:GetAttribute("Game1RescueMapId")
        if type(mapId)~="string" then mapId=Http:GenerateGUID(false); f:SetAttribute("Game1RescueMapId",mapId) end
        return mapId
    end
    local function syncDatabase()
        local f=root(false); assert(f,"No saved route map to synchronize")
        local mapId=ensureMapId(f)
        local payload={}
        for _,route in ipairs(records(f)) do
            local coords={}; for _,p in ipairs(read(route)) do table.insert(coords,{p.X,p.Y,p.Z}) end
            local name,catalog=metadata(route)
            table.insert(payload,{id=route.Name,points=coords,name=name,catalog=catalog})
        end
        local response=Http:RequestAsync({Url="http://127.0.0.1:43821/api/rescue-routes/studio-sync",Method="POST",
            Headers={["X-Control-Token"]="Game1LocalControlV1",["Content-Type"]="application/json"},
            Body=Http:JSONEncode({mapId=mapId,placeId=game.PlaceId,routes=payload})})
        assert(response.Success,"Place changed locally, Database sync failed: "..response.Body)
        status.Text="Database synchronized · "..#payload.." routes. Save Place before Play."
    end
    local function clearPreview()
        if preview then preview:Destroy(); preview=nil end
    end
    refreshPreview=function()
        clearPreview()
        if not dock.Enabled or RunService:IsRunning() then return end
        preview=Instance.new("Folder"); preview.Name="Game1RescueRoutePreview"; preview.Archivable=false; preview.Parent=Workspace
        local function part(cf,size,color)
            local p=Instance.new("Part"); p.Archivable=false; p.Anchored=true; p.CanCollide=false; p.CanTouch=false; p.CanQuery=false; p.CastShadow=false
            p.Material=Enum.Material.Neon; p.Color=color; p.Size=size; p.CFrame=cf; p.Parent=preview
        end
        local function draw(list,color,width)
            for i,p in ipairs(list) do
                local a=p+Vector3.yAxis*.15
                part(CFrame.new(a),Vector3.one*width*3,color)
                if i>1 then
                    local b=list[i-1]+Vector3.yAxis*.15; local d=(a-b).Magnitude
                    if d>.01 then part(CFrame.lookAt((a+b)/2,a,if math.abs((a-b).Unit.Y)>.99 then Vector3.xAxis else Vector3.yAxis),Vector3.new(width,width,d),color) end
                end
            end
        end
        for _,route in ipairs(records(root(false))) do
            if not draft or route~=draft.route then
                local selected=route==selectedRoute
                draw(read(route),if selected then Color3.fromRGB(255,205,72) else Color3.fromRGB(38,157,224),if selected then .24 else .1)
            end
        end
        if draft then draw(draft.points,Color3.fromRGB(100,235,141),.16) end
    end
    local function stopDrawing() if drawing then drawing=false; plugin:Deactivate() end end
    local function startDrawing() drawing=true; plugin:Activate(true) end
    local function redraw() refreshList(); refreshControls(); refreshPreview() end
    local function draftStatus()
        if draft then status.Text=(if drawing then "Click map · " else "Draft paused · ")..#draft.points.." points. Green = draft." end
    end
    local newButton=line("+ New route",function()
        assert(not draft,"Apply or cancel the current draft first")
        local catalog=DEFAULT_CATALOG
        if isRoute(selectedRoute,root(false)) then local _,c=metadata(selectedRoute); catalog=c end
        selectedRoute=nil; pendingDelete=nil; draft={points={},catalog=catalog}; startDrawing(); redraw(); draftStatus()
    end)
    label("Saved routes · click to select (yellow)",24)
    local list=Instance.new("Frame"); list.Size=UDim2.new(1,-6,0,0); list.AutomaticSize=Enum.AutomaticSize.Y; list.BackgroundTransparency=1; place(list)
    local listLayout=Instance.new("UIListLayout"); listLayout.SortOrder=Enum.SortOrder.LayoutOrder; listLayout.Padding=UDim.new(0,3); listLayout.Parent=list
    local editButton=line("Edit selected route",function()
        assert(not draft and isRoute(selectedRoute,root(false)),"Select a saved route in the list")
        local name,catalog=metadata(selectedRoute)
        pendingDelete=nil; draft={route=selectedRoute,points=read(selectedRoute),name=name,catalog=catalog}; startDrawing(); redraw(); draftStatus()
    end)
    local deleteButton=line("Delete selected route",function()
        local f=root(false); local route=selectedRoute
        assert(not draft and isRoute(route,f),"Select a saved route in the list; cancel draft first")
        if pendingDelete~=route then pendingDelete=route; local name,catalog=metadata(route); status.Text="Confirm deletion: "..catalog.." / "..name; return end
        -- The exact selected child is the only deletion target. Never delete a root/catalog.
        local backup=route:Clone(); assert(backup,"Route could not be backed up")
        History:SetWaypoint("Before Delete Rescue Route")
        if deleted then deleted.copy:Destroy() end
        deleted={copy=backup,root=f}; route:Destroy(); selectedRoute=nil; pendingDelete=nil
        History:SetWaypoint("Delete Rescue Route"); redraw(); syncDatabase()
    end)
    local cancelDeleteButton=line("Cancel deletion",function() pendingDelete=nil; status.Text="Deletion cancelled" end)
    local undoDeleteButton=line("Undo last deletion",function()
        local f=root(false); assert(not draft and deleted and deleted.root==f,"No deleted route to restore in this map")
        local route=deleted.copy; assert(not f:FindFirstChild(route.Name),"Route already exists; no data overwritten")
        History:SetWaypoint("Before Restore Rescue Route"); route.Parent=f; deleted=nil; selectedRoute=route; pendingDelete=nil
        local _,catalog=metadata(route); collapsed[catalog]=nil
        History:SetWaypoint("Restore Rescue Route"); redraw(); syncDatabase()
    end)
    local editor=Instance.new("Frame"); editor.Size=UDim2.new(1,-6,0,0); editor.AutomaticSize=Enum.AutomaticSize.Y; editor.BackgroundTransparency=1; place(editor)
    local editorLayout=Instance.new("UIListLayout"); editorLayout.SortOrder=Enum.SortOrder.LayoutOrder; editorLayout.Padding=UDim.new(0,4); editorLayout.Parent=editor
    local function field(title)
        label(title,20,editor)
        local t=Instance.new("TextBox"); t.Size=UDim2.new(1,-6,0,29); t.BackgroundColor3=Color3.fromRGB(44,56,68); t.TextColor3=Color3.new(1,1,1); t.ClearTextOnFocus=false; t.Font=Enum.Font.Gotham; t.TextSize=12; place(t,editor); return t
    end
    label("Click an existing line to connect · snap 1 stud / same height",36,editor)
    local nameBox=field("Route name")
    local catalogBox=field("Catalog · existing or new name")
    nameBox:GetPropertyChangedSignal("Text"):Connect(function() if draft then draft.name=nameBox.Text end end)
    catalogBox:GetPropertyChangedSignal("Text"):Connect(function() if draft then draft.catalog=catalogBox.Text end end)
    local resumeButton=line("Resume drawing",function() assert(draft); startDrawing(); draftStatus() end,editor)
    local undoPointButton=line("Undo last point",function() assert(draft); table.remove(draft.points); refreshPreview(); draftStatus() end,editor)
    local closeLoopButton=line("Close loop",function()
        assert(draft); local points=draft.points
        if #points>=3 and #points<256 and (points[1]-points[#points]).Magnitude>.01 then table.insert(points,points[1]) end
        refreshPreview(); draftStatus()
    end,editor)
    local applyButton=line("Apply · Save route",function()
        assert(draft and #draft.points>=2,"At least two points required")
        local routeId=if draft.route then draft.route.Name else "Route_"..Http:GenerateGUID(false)
        local name=cleanText(draft.name or "","Route "..routeId:sub(7,14))
        local catalog=cleanText(draft.catalog or "",DEFAULT_CATALOG)
        local f=root(false)
        if draft.route then assert(isRoute(draft.route,f),"Edited route was removed; cancel draft") end
        local count,edges=0,0
        for _,r in ipairs(records(f)) do if r~=draft.route then count+=1; edges+=#read(r)-1 end end
        assert(count<512 and edges+#draft.points-1<=2048,"Map limit: 512 routes / 2048 edges")
        stopDrawing(); History:SetWaypoint("Before Rescue Route")
        f=root(true); ensureMapId(f); local route=draft.route or Instance.new("Folder")
        if not draft.route then route.Name=routeId end
        route:SetAttribute("RouteDisplayName",name); route:SetAttribute("RouteCatalog",catalog)
        for _,v in ipairs(route:GetChildren()) do if v:IsA("Vector3Value") and tonumber(v.Name) then v:Destroy() end end
        for i,p in ipairs(draft.points) do local v=Instance.new("Vector3Value"); v.Name=tostring(i); v.Value=p; v.Parent=route end
        route.Parent=f; History:SetWaypoint("Save Rescue Route")
        selectedRoute=route; draft=nil; pendingDelete=nil; collapsed[catalog]=nil; redraw(); syncDatabase()
    end,editor)
    line("Cancel draft",function()
        assert(draft); stopDrawing(); selectedRoute=if isRoute(draft.route,root(false)) then draft.route else nil; draft=nil; pendingDelete=nil
        redraw(); status.Text="Draft discarded. Saved routes unchanged."
    end,editor)
    line("Sync Database",function() assert(not draft,"Apply or cancel draft first"); syncDatabase() end)
    line("Navigation · cycle Place override",function()
        local override=Workspace:GetAttribute("Game1ExperimentalMonsterNavigation")
        if override==nil then Workspace:SetAttribute("Game1ExperimentalMonsterNavigation",false); status.Text="Legacy navigation on next Play"
        elseif override==false then Workspace:SetAttribute("Game1ExperimentalMonsterNavigation",true); status.Text="Experimental navigation on next Play"
        else Workspace:SetAttribute("Game1ExperimentalMonsterNavigation",nil); status.Text="Use Options on next Play" end
    end)
    local function selectRoute(route)
        assert(not draft and isRoute(route,root(false)),"Cancel or apply the draft first")
        local name,catalog=metadata(route)
        if selectedRoute==route then selectedRoute=nil; pendingDelete=nil; redraw(); status.Text="Selection cleared"; return end
        selectedRoute=route; pendingDelete=nil; redraw(); status.Text="Selected: "..catalog.." / "..name
    end
    refreshList=function()
        for _,child in ipairs(list:GetChildren()) do if child~=listLayout then child:Destroy() end end
        local f=root(false)
        if not isRoute(selectedRoute,f) then selectedRoute=nil; pendingDelete=nil end
        local all=records(f); local current=nil
        if #all==0 then label("No saved routes",24,list) end
        for _,route in ipairs(all) do
            local name,catalog=metadata(route)
            if catalog~=current then
                current=catalog
                line((if collapsed[catalog] then "+ " else "− ")..catalog,function()
                    collapsed[catalog]=not collapsed[catalog]
                    if collapsed[catalog] and not draft and isRoute(selectedRoute,root(false)) then
                        local _,selectedCatalog=metadata(selectedRoute)
                        if selectedCatalog==catalog then selectedRoute=nil; pendingDelete=nil end
                    end
                    redraw()
                end,list)
            end
            if not collapsed[catalog] then
                local b=line((if selectedRoute==route then "● " else "    ")..name.." · "..#read(route).." pts",function() selectRoute(route) end,list)
                if selectedRoute==route then b.BackgroundColor3=Color3.fromRGB(113,91,37) end
                enabled(b,not draft)
            end
        end
    end
    refreshControls=function()
        local hasSelection=isRoute(selectedRoute,root(false)) and not draft
        enabled(newButton,not draft); enabled(editButton,hasSelection); enabled(deleteButton,hasSelection)
        deleteButton.Text=if pendingDelete then "Confirm delete selected route" else "Delete selected route"
        cancelDeleteButton.Visible=pendingDelete~=nil
        enabled(undoDeleteButton,not draft and deleted~=nil and deleted.root==root(false))
        editor.Visible=draft~=nil
        if draft then
            if nameBox.Text~=(draft.name or "") then nameBox.Text=draft.name or "" end
            if catalogBox.Text~=draft.catalog then catalogBox.Text=draft.catalog end
            enabled(resumeButton,not drawing); enabled(undoPointButton,#draft.points>0); enabled(closeLoopButton,#draft.points>=3 and #draft.points<256); enabled(applyButton,#draft.points>=2)
        end
    end
    mouse.Button1Down:Connect(function()
        if busy or not draft or not drawing or not dock.Enabled or RunService:IsRunning() or not mouse.Target then return end
        local points=draft.points
        if #points>=256 then status.Text="Maximum 256 points per route"; return end
        local p,connected=snapPoint(mouse.Hit.Position,records(root(false)),draft.route)
        if #points==0 or (points[#points]-p).Magnitude>.05 then
            table.insert(points,p); refreshPreview(); refreshControls(); draftStatus()
            if connected then local name,catalog=metadata(connected); status.Text="Junction · "..catalog.." / "..name.." · "..#points.." points" end
        end
    end)
    plugin.Deactivation:Connect(function() drawing=false; if dock.Enabled then refreshControls(); draftStatus() end end)
    button.Click:Connect(function() dock.Enabled=not dock.Enabled end)
    dock:GetPropertyChangedSignal("Enabled"):Connect(function() if not dock.Enabled then stopDrawing(); clearPreview() else redraw(); draftStatus() end end)
    local function historyChanged()
        stopDrawing(); draft=nil; selectedRoute=nil; pendingDelete=nil
        if deleted then deleted.copy:Destroy(); deleted=nil end
        if dock.Enabled then redraw(); status.Text="Studio history changed. Sync Database to update the mirror." end
    end
    History.OnUndo:Connect(historyChanged); History.OnRedo:Connect(historyChanged)
    plugin.Unloading:Connect(function() stopDrawing(); clearPreview(); if deleted then deleted.copy:Destroy() end end)
    RunService.Heartbeat:Connect(function() if RunService:IsRunning() and preview then drawing=false; clearPreview() end end)
    if dock.Enabled then redraw() else refreshControls() end
end
return Routes
