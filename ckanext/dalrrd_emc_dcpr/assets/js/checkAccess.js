"use strict";

ckan.module("check-access", function ($){
    return {
        initialize: function(){
            $.proxyAll(this,/_on/);

            const newDataset = document.querySelector('.new-dataset');
            const xmlUpload = document.querySelector('.xml-upload');
            const harvesting = document.querySelector('.harvesting');
            newDataset.addEventListener("click", this._onClick)
            xmlUpload.addEventListener("click", this._onClick)
            harvesting.addEventListener("click", this._onClick)

        },

        _onClick: function (event) {
            const logged = this.el.data('logged');
            const itself = event.target.closest("[data-link]")
            if(logged === 'False'){
                itself.href='/user/login';
                itself.click();
            }
        }
    }


})
