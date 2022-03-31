import logging

from flask import Blueprint, redirect, request
from ckan.plugins import toolkit
from ckan.lib.search import SearchError, SearchQueryError
import ckan.lib.helpers as h
from ckan.logic import clean_dict, parse_params, tuplize_dict
import ckan.lib.navl.dictization_functions as dict_fns

logger = logging.getLogger(__name__)

dcpr_blueprint = Blueprint(
    "dcpr", __name__, template_folder="templates", url_prefix="/dcpr"
)


@dcpr_blueprint.route("/")
def dcpr_home():
    logger.debug("Inside the dcpr_home view")
    existing_requests = toolkit.get_action("dcpr_request_list")(data_dict={})

    return toolkit.render(
        "dcpr/index.html", extra_vars={"dcpr_requests": existing_requests}
    )


@dcpr_blueprint.route("/request/new", methods=["GET", "POST"])
def dcpr_request_new():
    logger.debug("Inside the dcpr_new_request view")
    context = {
        u"user": toolkit.g.user,
        u"auth_user_obj": toolkit.g.userobj,
    }
    if request.method == "POST":
        try:
            data_dict = clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.form)))
            )
            data_dict["owner_user"] = toolkit.g.userobj.id
            data_dict["csi_moderator"] = None
            data_dict["nsif_reviewer"] = None
            data_dict["spatial_extent"] = None

        except dict_fns.DataError:
            return toolkit.base.abort(400, toolkit._(u"Integrity Error"))
        try:
            dcpr_request = toolkit.get_action("dcpr_request_create")(context, data_dict)

            url = toolkit.h.url_for(
                "{0}.dcpr_request_show".format("dcpr"),
                request_id=dcpr_request.csi_reference_id,
            )
            return toolkit.h.redirect_to(url)

        except toolkit.NotAuthorized:
            return toolkit.base.abort(
                403, toolkit._(u"Unauthorized to create DCPR request")
            )
        except toolkit.ObjectNotFound as e:
            return toolkit.base.abort(404, toolkit._(u"DCPR request not found"))
        except toolkit.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary

            request.method = "GET"
            return dcpr_request_edit(None, data_dict, errors, error_summary)

        url = toolkit.h.url_for(
            "{0}.dcpr_request_show".format("dcpr"),
            request_id=dcpr_request.csi_reference_id,
        )
        return toolkit.h.redirect_to(url)

    else:
        try:
            toolkit.check_access("dcpr_request_create_auth", context)
        except toolkit.NotAuthorized:
            return toolkit.base.abort(
                403,
                toolkit._(u"User %r not authorized to create DCPR requests")
                % (toolkit.g.user),
            )

        return toolkit.render("dcpr/new.html", extra_vars={"dcpr_request": None})


@dcpr_blueprint.route("/search")
def dcpr_search():
    logger.debug("Inside the dcpr_search view")
    extra_vars = {}

    extra_vars[u"q"] = q = toolkit.request.args.get(u"q", u"")
    page = toolkit.h.get_page_number(toolkit.request.args)

    limit = toolkit.config.get(u"ckan.dcpr_requests_per_page") or 10
    data = {u"q": q, u"rows": limit, u"start": (page - 1) * limit}
    try:

        existing_requests = toolkit.get_action("dcpr_request_search")(data_dict=data)
        extra_vars["requests"] = existing_requests

        extra_vars[u"page"] = h.Page(
            collection=existing_requests[u"results"],
            page=page,
            item_count=existing_requests[u"count"],
            items_per_page=limit,
        )

    except SearchQueryError as error:
        logger.info("Request search query rejected: %r", error.args)
        toolkit.base.abort(
            400,
            toolkit._("Invalid search query: {error_message}").format(
                error_message=str(error)
            ),
        )
    except SearchError as error:
        # May be bad input from the user, but may also be more serious like
        # bad code causing a SOLR syntax error, or a problem connecting to
        # SOLR
        logger.error("Request search error: %r", error.args)
        extra_vars["query_error"] = True
        extra_vars["page"] = h.Page(collection=[])

    return toolkit.render("dcpr/index.html", extra_vars=extra_vars)


@dcpr_blueprint.route("/request/<request_id>")
def dcpr_request_show(request_id):
    logger.debug("Inside the dcpr_request_show view")
    data_dict = {"id": request_id}
    extra_vars = {}

    nsif_reviewer = toolkit.h["emc_user_is_org_member"](
        "nsif", toolkit.g.userobj, role="editor"
    )
    csi_reviewer = toolkit.h["emc_user_is_org_member"](
        "csi", toolkit.g.userobj, role="editor"
    )

    extra_vars["nsif_reviewer"] = nsif_reviewer
    extra_vars["csi_reviewer"] = csi_reviewer

    try:
        dcpr_request = toolkit.get_action("dcpr_request_show")(data_dict=data_dict)
        request_owner = (
            dcpr_request["owner_user"] == toolkit.g.userobj.id
            if toolkit.g.userobj
            else False
        )

        extra_vars["dcpr_request"] = dcpr_request
        extra_vars["request_owner"] = request_owner

    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        return toolkit.base.abort(404, toolkit._("Request not found"))

    return toolkit.render("dcpr/show.html", extra_vars=extra_vars)


@dcpr_blueprint.route("/request/edit/<request_id>", methods=["GET", "POST"])
def dcpr_request_edit(request_id, data=None, errors=None, error_summary=None):
    logger.debug("Inside the dcpr_request_edit view")
    data_dict = {"id": request_id}
    extra_vars = {}
    extra_vars["errors"] = errors

    context = {
        u"user": toolkit.g.user,
        u"auth_user_obj": toolkit.g.userobj,
    }

    if request.method == "GET":
        try:
            if request_id is not None:
                dcpr_request = toolkit.get_action("dcpr_request_show")(
                    data_dict=data_dict
                )
                extra_vars["dcpr_request"] = dcpr_request
            elif data is not None:
                extra_vars["dcpr_request"] = data
                extra_vars["error_summary"] = error_summary

            nsif_reviewer = toolkit.h["emc_user_is_org_member"](
                "nsif", toolkit.g.userobj, role="editor"
            )
            csi_reviewer = toolkit.h["emc_user_is_org_member"](
                "csi", toolkit.g.userobj, role="editor"
            )

            extra_vars["nsif_reviewer"] = nsif_reviewer
            extra_vars["csi_reviewer"] = csi_reviewer

        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            return toolkit.base.abort(404, toolkit._("Request not found"))

        try:
            if request_id:
                toolkit.check_access(
                    "dcpr_request_edit_auth", context, {"request_id": request_id}
                )
            else:
                toolkit.check_access("dcpr_request_create_auth", context, data_dict)

        except toolkit.NotAuthorized:
            return toolkit.base.abort(
                403,
                toolkit._(u"User %r not authorized to edit DCPR requests")
                % (toolkit.g.user),
            )

        return toolkit.render("dcpr/edit.html", extra_vars=extra_vars)

    else:
        try:
            data_dict = clean_dict(
                dict_fns.unflatten(tuplize_dict(parse_params(request.form)))
            )
            data_dict["csi_moderator"] = None
            data_dict["nsif_reviewer"] = None
            data_dict["spatial_extent"] = None
        except dict_fns.DataError:
            return toolkit.base.abort(400, toolkit._(u"Integrity Error"))
        try:
            dcpr_request = toolkit.get_action("dcpr_request_update")(context, data_dict)

            url = toolkit.h.url_for(
                "{0}.dcpr_request_show".format("dcpr"), request_id=request_id
            )
            return toolkit.h.redirect_to(url)

        except toolkit.NotAuthorized as e:
            return toolkit.base.abort(
                403,
                toolkit._("Unauthorized to perfom the action, %s") % e,
            )
        except toolkit.ObjectNotFound as e:
            return toolkit.base.abort(404, toolkit._(u"DCPR request not found"))
        except toolkit.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary

            return dcpr_request_edit(
                data_dict.get("request_id", None), data_dict, errors, error_summary
            )

        url = toolkit.h.url_for(
            "{0}.dcpr_request_show".format("dcpr"), request_id=request_id
        )
        return toolkit.h.redirect_to(url)


@dcpr_blueprint.route("/request/delete/<request_id>", methods=["GET", "POST"])
def dcpr_request_delete(request_id, errors=None, error_summary=None):
    logger.debug("Inside the dcpr_request_delete view")
    data_dict = {"request_id": request_id}
    extra_vars = {}

    context = {
        u"user": toolkit.g.user,
        u"auth_user_obj": toolkit.g.userobj,
    }

    if request.method == "GET":
        try:
            toolkit.check_access(
                "dcpr_request_delete_auth", context, {"request_id": request_id}
            )
        except toolkit.NotAuthorized:
            return toolkit.base.abort(
                403,
                toolkit._(u"User %r not authorized to delete DCPR requests")
                % (toolkit.g.user),
            )

        return toolkit.render("dcpr/delete.html", extra_vars=extra_vars)

    else:
        try:
            dcpr_request = toolkit.get_action("dcpr_request_delete")(context, data_dict)

            url = toolkit.h.url_for("{0}.dcpr_home".format("dcpr"))
            return toolkit.h.redirect_to(url)

        except toolkit.NotAuthorized as e:
            return toolkit.base.abort(
                403,
                toolkit._("Unauthorized to perfom the action, %s") % e,
            )
        except toolkit.ObjectNotFound as e:
            return toolkit.base.abort(404, toolkit._(u"DCPR request not found"))
        except toolkit.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return dcpr_request_edit(
                dcpr_request.csi_reference_id, errors, error_summary
            )

        url = toolkit.h.url_for("{0}.dcpr_home".format("dcpr"))
        return toolkit.h.redirect_to(url)
