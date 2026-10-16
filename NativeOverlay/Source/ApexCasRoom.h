#pragma once
#include "ApexUiData.h"
#include <set>

namespace td1::ui {
inline bool CasRoomDocument(const Json& room, const Json& client, const std::string& sim) {
    if (!CasDocument(client, sim) || !room.is_object() || room.value("schema",Json()) != 1 ||
        room.value("scope",Json()) != "captured-cas-room-inventory" || Scalar(room,"sim_id") != sim ||
        Scalar(room,"household_id") != Scalar(client["sim"],"householdId") ||
        !room.contains("save_guid") || !ExactUint64Identity(room["save_guid"]) ||
        room.value("all_captured_forms_visible",Json()) != true ||
        room.value("all_forms_editable_this_visit",Json()) != false ||
        room.value("membership_modified",Json()) != false || room.value("mapping_verified",Json()) != false ||
        room.value("alternate_accept_authorized",Json()) != false ||
        room.value("appearance_persistence_verified",Json()) != false ||
        !room.contains("rows") || !room["rows"].is_array() || room["rows"].empty() || room["rows"].size()>32 ||
        !room.contains("native_session") || !room["native_session"].is_number_integer() || room["native_session"]<=0 ||
        !client.contains("owner_pair_observation") || !client["owner_pair_observation"].is_object() ||
        room["native_session"] != client["owner_pair_observation"].value("session",Json()) ||
        room.value("selected_layer",Json()) != client["sim"].value("occultLayer",Json()) ||
        room.value("selected_form",Json()) != client["sim"].value("occultType",Json())) return false;
    const auto nativeLayers=room.find("native_layers");
    if (nativeLayers!=room.end()) {
        if (!nativeLayers->is_array() || nativeLayers->size()!=2 || room.value("native_layer_selection_only",Json())!=true) return false;
        int selectedLayers=0;
        for (size_t i=0;i<2;++i) {
            const auto& row=(*nativeLayers)[i];
            if (!row.is_object() || row.value("layer",Json())!=i || !row["layer"].is_number_integer() ||
                Scalar(row,"sim_id")!=sim || !row.contains("form_flags") || !row["form_flags"].is_number_integer() ||
                !row.contains("label") || !row["label"].is_string() || row["label"].get<std::string>().empty() ||
                row["label"].get<std::string>().size()>128 || row.value("navigation_supported",Json())!=true ||
                !row.contains("selected") || !row["selected"].is_boolean()) return false;
            const auto form=row["form_flags"].get<int64_t>();
            if (form<=0 || form>64 || (form&(form-1))!=0) return false;
            if (row["selected"]==true) {
                ++selectedLayers;
                if (row["layer"]!=room["selected_layer"] || row["form_flags"]!=room["selected_form"]) return false;
            } else if (row["layer"]==room["selected_layer"]) return false;
        }
        if (selectedLayers!=1) return false;
    }
    std::set<int64_t> forms; std::set<std::string> owners; int selected=0;
    for (const auto& row:room["rows"]) {
        if (!row.is_object() || !row.contains("form_flags") || !row["form_flags"].is_number_integer() ||
            !row.contains("captured_owner_id") || !ExactUint64Identity(row["captured_owner_id"]) ||
            Scalar(row,"captured_owner_id")==sim || !owners.insert(Scalar(row,"captured_owner_id")).second ||
            !row.contains("label") || !row["label"].is_string() || row["label"].get<std::string>().empty() ||
            row["label"].get<std::string>().size()>128 || row.value("visible",Json())!=true ||
            !row.contains("selected") || !row["selected"].is_boolean() ||
            !row.contains("navigation_supported") || !row["navigation_supported"].is_boolean() ||
            !row.contains("native_layer")) return false;
        const auto form=row["form_flags"].get<int64_t>();
        if (form<=0 || form>=(1LL<<31) || (form&(form-1))!=0 || !forms.insert(form).second) return false;
        const auto& layer=row["native_layer"];
        if (!layer.is_null() && (!layer.is_number_integer() || (layer!=0 && layer!=1))) return false;
        if (row["navigation_supported"]==true && layer.is_null()) return false;
        if (row["selected"]==true) {
            ++selected;
            if (row["form_flags"]!=room["selected_form"] ||
                (layer!=room["selected_layer"] && !(layer.is_null() && nativeLayers!=room.end()))) return false;
        }
    }
    if (nativeLayers!=room.end()) for (const auto& row:*nativeLayers)
        if (!forms.count(row["form_flags"].get<int64_t>())) return false;
    return selected==1;
}
}
